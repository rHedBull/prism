import * as THREE from 'three';
import { createScene, animate, animateCamera } from './scene.js';

const { scene, camera, renderer, controls } = createScene();

// Default camera position for reset
const defaultCameraPos = new THREE.Vector3(30, 40, 30);
const defaultTarget = new THREE.Vector3(0, 0, 0);

document.getElementById('btn-reset').addEventListener('click', () => {
    animateCamera(camera, controls, defaultCameraPos, defaultTarget);
});

animate(renderer, scene, camera, controls);

console.log('Scene initialized');
