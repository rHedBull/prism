import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import * as TWEEN from '@tweenjs/tween.js';
import { createRenderScheduler } from './render-scheduler.js';

// Panel state shared across modules
export const panelState = { left: true, right: true };

const LEFT_WIDTH = 280;
const RIGHT_WIDTH = 260;

export function getLeftOffset() {
    return panelState.left ? LEFT_WIDTH : 0;
}

export function getRightOffset() {
    return panelState.right ? RIGHT_WIDTH : 0;
}

export function getCanvasWidth() {
    return window.innerWidth - getLeftOffset() - getRightOffset();
}

export function createScene() {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8f6fc);
    scene.fog = new THREE.FogExp2(0xf8f6fc, 0.004);

    const canvasW = Math.max(1, getCanvasWidth());
    const canvasH = Math.max(1, window.innerHeight);
    const camera = new THREE.PerspectiveCamera(
        60, canvasW / canvasH, 0.1, 1000
    );
    camera.position.set(30, 40, 30);
    camera.lookAt(0, 0, 0);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(canvasW, canvasH);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.domElement.style.marginLeft = `${getLeftOffset()}px`;
    document.body.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    controls.minDistance = 5;
    controls.maxDistance = 200;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.6);
    directionalLight.position.set(20, 40, 20);
    scene.add(directionalLight);

    function resizeCanvas() {
        const w = Math.max(1, getCanvasWidth());
        const h = Math.max(1, window.innerHeight);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
        renderer.domElement.style.marginLeft = `${getLeftOffset()}px`;
    }

    window.addEventListener('resize', () => {
        resizeCanvas();
        requestRender();
    });

    return { scene, camera, renderer, controls, resizeCanvas };
}

let _scheduler = null;

export function requestRender() {
    if (_scheduler) _scheduler.requestRender();
}

export function initRenderer(renderer, scene, camera, controls) {
    _scheduler = createRenderScheduler({
        scheduleFrame: requestAnimationFrame,
        render: () => {
            TWEEN.update();
            renderer.render(scene, camera);
        },
        hasPendingWork: () => TWEEN.getAll().length > 0,
    });

    // Re-render on orbit/zoom
    controls.addEventListener('change', () => requestRender());

    // Initial render
    requestRender();
}

export function animateCamera(camera, controls, targetPos, targetLookAt, duration = 1000) {
    const startPos = camera.position.clone();
    const startTarget = controls.target.clone();

    new TWEEN.Tween({ t: 0 })
        .to({ t: 1 }, duration)
        .easing(TWEEN.Easing.Cubic.InOut)
        .onUpdate(({ t }) => {
            camera.position.lerpVectors(startPos, targetPos, t);
            controls.target.lerpVectors(startTarget, targetLookAt, t);
            requestRender();
        })
        .start();
    requestRender();
}
