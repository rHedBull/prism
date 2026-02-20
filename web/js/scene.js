import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import * as TWEEN from '@tweenjs/tween.js';

export function createScene() {
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8f6fc);
    scene.fog = new THREE.FogExp2(0xf8f6fc, 0.004);

    const camera = new THREE.PerspectiveCamera(
        60, window.innerWidth / window.innerHeight, 0.1, 1000
    );
    camera.position.set(30, 40, 30);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    document.body.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.minDistance = 5;
    controls.maxDistance = 200;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.6);
    directionalLight.position.set(20, 40, 20);
    scene.add(directionalLight);

    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    return { scene, camera, renderer, controls };
}

export function animate(renderer, scene, camera, controls) {
    function loop() {
        requestAnimationFrame(loop);
        controls.update();
        TWEEN.update();
        renderer.render(scene, camera);
    }
    loop();
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
        })
        .start();
}
