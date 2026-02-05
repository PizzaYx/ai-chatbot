<template>
    <div class="digital-human" ref="containerRef">
        <canvas ref="canvasRef"></canvas>
        <div v-if="isLoading" class="loading-overlay">
            <div class="spinner"></div>
            <p>加载数字人...</p>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const props = defineProps<{
    modelUrl?: string;
    isSpeaking?: boolean;
    audioElement?: HTMLAudioElement | null;
}>();

const containerRef = ref<HTMLDivElement | null>(null);
const canvasRef = ref<HTMLCanvasElement | null>(null);
const isLoading = ref(true);

let scene: THREE.Scene;
let camera: THREE.PerspectiveCamera;
let renderer: THREE.WebGLRenderer;
let controls: OrbitControls;
let mixer: THREE.AnimationMixer | null = null;
let morphTargetMeshes: THREE.Mesh[] = [];
let animationFrameId: number;
let audioContext: AudioContext | null = null;
let analyser: AnalyserNode | null = null;
let headBone: THREE.Bone | null = null;
let neckBone: THREE.Bone | null = null;
let spineBone: THREE.Bone | null = null;

// 默认使用本地模型 (请确保文件已存在于 public/models/avatar.glb)
const defaultModelUrl = '/models/avatar.glb';

const initScene = () => {
    if (!canvasRef.value || !containerRef.value) return;

    const width = containerRef.value.clientWidth;
    const height = containerRef.value.clientHeight;

    // 创建场景
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a2e);

    // 创建相机
    camera = new THREE.PerspectiveCamera(30, width / height, 0.1, 100);
    camera.position.set(0, 1.5, 2);

    // 创建渲染器
    renderer = new THREE.WebGLRenderer({
        canvas: canvasRef.value,
        antialias: true,
        alpha: true
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;

    // 添加控制器
    controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1.4, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 1;
    controls.maxDistance = 5;
    controls.update();

    // 添加灯光
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
    directionalLight.position.set(2, 3, 2);
    scene.add(directionalLight);

    const fillLight = new THREE.DirectionalLight(0xffffff, 0.3);
    fillLight.position.set(-2, 1, -1);
    scene.add(fillLight);

    // 加载模型
    loadModel(props.modelUrl || defaultModelUrl);

    // 开始动画循环
    animate();
};

const loadModel = (url: string) => {
    isLoading.value = true;
    const loader = new GLTFLoader();

    loader.load(
        url,
        (gltf) => {
            const model = gltf.scene;
            model.position.set(0, 0, 0);
            scene.add(model);

            // 找到包含 morph targets 的网格（用于口型同步）
            model.traverse((child) => {
                if (child instanceof THREE.Mesh && child.morphTargetInfluences) {
                    morphTargetMeshes.push(child);
                    console.log('🎭 Found morph mesh:', child.name);
                    // console.log('🎭 Morph targets:', Object.keys(child.morphTargetDictionary || {}));
                }

                // 查找骨骼
                if (child.name === 'Head') headBone = child as THREE.Bone;
                if (child.name === 'Neck') neckBone = child as THREE.Bone;
                if (child.name === 'Spine2') spineBone = child as THREE.Bone; // 胸部
            });

            if (headBone) console.log('🦴 Found Head Bone');
            if (neckBone) console.log('🦴 Found Neck Bone');

            console.log('🎭 Total morph meshes found:', morphTargetMeshes.length);

            // 播放动画（如果有）
            if (gltf.animations.length > 0) {
                mixer = new THREE.AnimationMixer(model);
                const action = mixer.clipAction(gltf.animations[0]);
                action.play();
            }

            isLoading.value = false;
        },
        undefined,
        (error) => {
            console.error('Error loading model:', error);

            // 如果加载本地模型失败，且当前不是远程模型，则尝试回退到远程模型
            if (url.startsWith('/models/') && url !== 'https://models.readyplayer.me/697c725bd1328e35da38db39.glb') {
                console.warn('⚠️ 本地模型加载失败，尝试回退到远程模型...');
                loadModel('https://models.readyplayer.me/697c725bd1328e35da38db39.glb');
            } else {
                isLoading.value = false;
            }
        }
    );
};

// 完整表情动画
let speakingTime = 0;
let blinkTimer = 0;
let lookTimer = 0;

// 所有 Viseme（口型）
const allVisemes = [
    'viseme_sil', 'viseme_PP', 'viseme_FF', 'viseme_TH', 'viseme_DD',
    'viseme_kk', 'viseme_CH', 'viseme_SS', 'viseme_nn', 'viseme_RR',
    'viseme_aa', 'viseme_E', 'viseme_I', 'viseme_O', 'viseme_U'
];
let currentVisemeIndex = 0;
let visemeChangeTimer = 0;

// 设置 morph target 值的辅助函数
const setMorph = (mesh: THREE.Mesh, name: string, value: number) => {
    if (!mesh.morphTargetDictionary || !mesh.morphTargetInfluences) return;
    const idx = mesh.morphTargetDictionary[name];
    if (idx !== undefined) {
        mesh.morphTargetInfluences[idx] = value;
    }
};

// 实时音频分析与丰富表情动效
const updateMouthShape = () => {
    if (morphTargetMeshes.length === 0) return;

    const dt = 0.016;
    speakingTime += dt;
    visemeChangeTimer += dt;
    blinkTimer += dt;
    lookTimer += dt;

    let mouthIntensity = 0;

    // 1. 获取实时音量
    if (analyser && props.isSpeaking) {
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(dataArray);

        // 计算平均音量 (取人声频率段，约 100Hz - 3000Hz)
        let sum = 0;
        const start = Math.floor(dataArray.length * 0.1); // 去掉极低频
        const end = Math.floor(dataArray.length * 0.7);   // 去掉极高频
        for (let i = start; i < end; i++) {
            sum += dataArray[i];
        }
        const average = sum / (end - start);

        // 音量映射到动作强度 (0-255 -> 0-1)
        // 增加灵敏度：* 2.0，基准值 -0.1
        mouthIntensity = Math.max(0, Math.min(1, (average / 255) * 2.0 - 0.1));
    } else if (props.isSpeaking) {
        // 降级方案：如果没有音频分析，使用模拟波形
        mouthIntensity = 0.3 + Math.sin(speakingTime * 8) * 0.2;
    }

    // 2. 决定当前口型 (Viseme Selection)
    if (props.isSpeaking) {
        // 每 0.08s - 0.15s 切换一次口型（接近语速）
        if (visemeChangeTimer > 0.08 + Math.random() * 0.07) {
            visemeChangeTimer = 0;

            // 根据音量选择合适的 Viseme 组
            if (mouthIntensity > 0.6) {
                // 大音量 -> 张大嘴 (aa, O, RR)
                const bigMouths = [10, 13, 9]; // aa, O, RR
                currentVisemeIndex = bigMouths[Math.floor(Math.random() * bigMouths.length)];
            } else if (mouthIntensity > 0.3) {
                // 中音量 -> 一般口型 (E, I, U, CH, TH)
                const midMouths = [11, 12, 14, 6, 3]; // E, I, U, CH, TH
                currentVisemeIndex = midMouths[Math.floor(Math.random() * midMouths.length)];
            } else {
                // 小音量 -> 闭合辅音 (PP, FF, DD, SS, nn, kk)
                const smallMouths = [1, 2, 4, 7, 8, 5]; // PP, FF, DD, SS, nn, kk
                currentVisemeIndex = smallMouths[Math.floor(Math.random() * smallMouths.length)];
            }
        }
    }

    // 3. 计算微表情强度
    const smileIntensity = 0.15 + Math.sin(speakingTime * 1.5) * 0.05; // 持续微笑
    const browIntensity = mouthIntensity * 0.4 + Math.sin(speakingTime * 2) * 0.1; // 眉毛随音量动
    const noseIntensity = mouthIntensity * 0.2; // 鼻子微动（大声时皱鼻）
    const cheekIntensity = smileIntensity * 0.5 + mouthIntensity * 0.1; // 脸颊跟随微笑和说话

    morphTargetMeshes.forEach((mesh) => {
        if (!mesh.morphTargetDictionary || !mesh.morphTargetInfluences) return;

        // === 口型 Viseme ===
        // 先快速淡出所有 viseme（让过渡更干脆，避免混成一团）
        allVisemes.forEach((viseme) => {
            const idx = mesh.morphTargetDictionary![viseme];
            if (idx !== undefined) {
                const fadeFactor = props.isSpeaking ? 0.5 : 0.2;
                mesh.morphTargetInfluences![idx] *= fadeFactor;
            }
        });

        if (props.isSpeaking) {
            // 平滑应用的强度
            const appliedIntensity = Math.max(0.1, mouthIntensity);

            // 应用当前 Viseme
            setMorph(mesh, allVisemes[currentVisemeIndex], appliedIntensity);

            // 辅助口型：混合一点 jawOpen (下巴) 让动作更明显
            setMorph(mesh, 'jawOpen', appliedIntensity * 0.4);

            // 辅助口型：大声说话时嘴角用力 (mouthShrug, mouthPress) - 避免呆板
            if (mouthIntensity > 0.5) {
                setMorph(mesh, 'mouthShrugUpper', mouthIntensity * 0.2);
            }
        } else {
            // 不说话时归零
            setMorph(mesh, 'jawOpen', 0);
            setMorph(mesh, 'mouthShrugUpper', 0);
        }

        // === 面部联动 (Facial Synergy) ===
        // 眉毛：大声说话时上扬 (Expressive)
        setMorph(mesh, 'browInnerUp', Math.max(0, browIntensity));
        setMorph(mesh, 'browOuterUpLeft', Math.max(0, browIntensity * 0.6));
        setMorph(mesh, 'browOuterUpRight', Math.max(0, browIntensity * 0.6));

        // 微笑：保持亲和力
        setMorph(mesh, 'mouthSmile', smileIntensity);
        setMorph(mesh, 'mouthSmileLeft', smileIntensity * 0.5);
        setMorph(mesh, 'mouthSmileRight', smileIntensity * 0.5);

        // 脸颊：微笑时鼓起 (Cheek Squint)
        setMorph(mesh, 'cheekSquintLeft', cheekIntensity);
        setMorph(mesh, 'cheekSquintRight', cheekIntensity);

        // 鼻子：用力说话时微皱 (Nose Sneer) - 增加真实感
        setMorph(mesh, 'noseSneerLeft', noseIntensity);
        setMorph(mesh, 'noseSneerRight', noseIntensity);

        // === 眼神互动 (Eye Contact) ===
        // 自动眨眼（每 2-5 秒）
        if (blinkTimer > 2 + Math.random() * 3) {
            blinkTimer = 0;
        }
        // 快速眨眼 (0.12s)
        const blinkValue = blinkTimer < 0.12 ? Math.sin(blinkTimer / 0.12 * Math.PI) : 0;
        setMorph(mesh, 'eyeBlinkLeft', blinkValue);
        setMorph(mesh, 'eyeBlinkRight', blinkValue);

        // 眼球微动（模拟扫视，避免死盯着看）
        if (lookTimer > 1.5 + Math.random() * 2) {
            lookTimer = 0;
        }
        // 动作幅度很小 (0.1)，主要在中间晃动
        const lookX = Math.sin(lookTimer * 2) * 0.08;
        const lookY = Math.cos(lookTimer * 1.5) * 0.05;

        setMorph(mesh, 'eyeLookInLeft', Math.max(0, lookX));
        setMorph(mesh, 'eyeLookOutLeft', Math.max(0, -lookX));
        setMorph(mesh, 'eyeLookInRight', Math.max(0, -lookX));
        setMorph(mesh, 'eyeLookOutRight', Math.max(0, lookX));

        // 说话向上看一点 (思考状)
        const thinkLook = props.isSpeaking ? 0.05 : 0;
        setMorph(mesh, 'eyeLookUpLeft', Math.max(0, lookY + thinkLook));
        setMorph(mesh, 'eyeLookUpRight', Math.max(0, lookY + thinkLook));
        setMorph(mesh, 'eyeLookDownLeft', Math.max(0, -lookY));
        setMorph(mesh, 'eyeLookDownRight', Math.max(0, -lookY));
    });

    // === 骨骼动画 (Head & Neck) ===
    // Idle 基础晃动 (像呼吸一样微弱 - 稍微加大一点以便可见)
    const idleX = Math.sin(speakingTime * 0.8) * 0.04; // 点头 0.02 -> 0.04
    const idleY = Math.cos(speakingTime * 0.4) * 0.04; // 转头 0.02 -> 0.04 (调慢频率)
    const idleZ = Math.sin(speakingTime * 0.6) * 0.02; // 歪头

    // 说话时的点头/晃动 (大幅减小，避免抽搐)
    let speakX = 0, speakY = 0, speakZ = 0;
    if (props.isSpeaking) {
        // 说话时稍微点头 (-x) 
        speakX = Math.sin(speakingTime * 6) * mouthIntensity * 0.04; // 0.1 -> 0.04
        // 说话时稍微歪头
        speakZ = Math.cos(speakingTime * 4) * mouthIntensity * 0.03; // 0.05 -> 0.03
        // 说话时稍微转头
        speakY = Math.sin(speakingTime * 2.5) * mouthIntensity * 0.03; // 0.05 -> 0.03
    }

    if (neckBone) {
        // 脖子主要负责大范围的转动和点头
        // 增加一点基础偏移，让姿态更自然
        neckBone.rotation.x = Math.max(-0.2, Math.min(0.2, idleX * 0.5 + speakX * 0.3));
        neckBone.rotation.y = Math.max(-0.3, Math.min(0.3, idleY * 0.5 + speakY * 0.3));
        neckBone.rotation.z = Math.max(-0.1, Math.min(0.1, idleZ * 0.3 + speakZ * 0.3));
    }

    if (headBone) {
        // 头部负责更灵敏的动作
        // 脖子动了，头要反向一点动，保持视线稳定 (LookAt 效果)
        headBone.rotation.x = Math.max(-0.15, Math.min(0.15, -idleX * 0.3 + speakX));
        headBone.rotation.y = Math.max(-0.2, Math.min(0.2, idleY + speakY));
        headBone.rotation.z = Math.max(-0.1, Math.min(0.1, idleZ * 0.5 + speakZ));
    }

    if (spineBone) {
        // 胸部微动（呼吸感）
        spineBone.rotation.x = Math.sin(speakingTime * 1.5) * 0.02;
    }
};

// 重置所有表情
const resetMouth = () => {
    const allMorphs = [
        ...allVisemes,
        'jawOpen', 'mouthOpen', 'mouthSmile', 'mouthSmileLeft', 'mouthSmileRight',
        'browInnerUp', 'browOuterUpLeft', 'browOuterUpRight', 'browDownLeft', 'browDownRight',
        'eyeBlinkLeft', 'eyeBlinkRight',
        'eyeLookInLeft', 'eyeLookOutLeft', 'eyeLookInRight', 'eyeLookOutRight',
        'eyeLookUpLeft', 'eyeLookUpRight', 'eyeLookDownLeft', 'eyeLookDownRight',
        'cheekSquintLeft', 'cheekSquintRight', 'cheekPuff',
        'noseSneerLeft', 'noseSneerRight'
    ];

    morphTargetMeshes.forEach((mesh) => {
        allMorphs.forEach((name) => setMorph(mesh, name, 0));
    });

    speakingTime = 0;
    visemeChangeTimer = 0;
    blinkTimer = 0;
    lookTimer = 0;
    currentVisemeIndex = 0;
};

// 设置音频分析
const setupAudioAnalysis = (audio: HTMLAudioElement) => {
    if (!audioContext) {
        audioContext = new AudioContext();
    }

    const source = audioContext.createMediaElementSource(audio);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;

    source.connect(analyser);
    analyser.connect(audioContext.destination);
};

const animate = () => {
    animationFrameId = requestAnimationFrame(animate);

    if (mixer) {
        mixer.update(0.016);
    }

    // 始终更新动画（包括口型和骨骼），以支持待机动作
    updateMouthShape();

    controls.update();
    renderer.render(scene, camera);
};

const handleResize = () => {
    if (!containerRef.value || !camera || !renderer) return;

    const width = containerRef.value.clientWidth;
    const height = containerRef.value.clientHeight;

    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
};

// 监听音频元素变化
watch(() => props.audioElement, (audio) => {
    if (audio) {
        setupAudioAnalysis(audio);
    }
});

// 监听说话状态变化
watch(() => props.isSpeaking, (speaking) => {
    console.log('🎭 isSpeaking changed:', speaking);
    if (!speaking) {
        resetMouth();
    }
});

onMounted(() => {
    initScene();
    window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
    window.removeEventListener('resize', handleResize);
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
    }
    if (renderer) {
        renderer.dispose();
    }
    if (audioContext) {
        audioContext.close();
    }
});
</script>

<style scoped lang="scss">
.digital-human {
    width: 100%;
    height: 300px;
    position: relative;
    border-radius: 16px;
    overflow: hidden;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);

    canvas {
        width: 100%;
        height: 100%;
        display: block;
    }
}

.loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(26, 26, 46, 0.9);
    color: white;

    .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(255, 255, 255, 0.2);
        border-top-color: #10b981;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        margin-bottom: 12px;
    }

    p {
        font-size: 14px;
        color: rgba(255, 255, 255, 0.7);
    }
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}
</style>
