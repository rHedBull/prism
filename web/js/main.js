import * as THREE from 'three';
import { createScene, animate, animateCamera } from './scene.js';
import { loadGraph, groupByAbstractionLevel } from './graph-loader.js';
import { createLayers } from './layers.js';
import { createEdges } from './edges.js';

const { scene, camera, renderer, controls } = createScene();

const defaultCameraPos = new THREE.Vector3(30, 40, 30);
const defaultTarget = new THREE.Vector3(0, 10, 0);

camera.position.copy(defaultCameraPos);
controls.target.copy(defaultTarget);

document.getElementById('btn-reset').addEventListener('click', () => {
    animateCamera(camera, controls, defaultCameraPos, defaultTarget);
});

async function init() {
    try {
        const graph = await loadGraph('..');
        const layerGroups = groupByAbstractionLevel(graph.nodes);
        const { layerMeshes, nodeMeshes, nodeDataMap } = createLayers(layerGroups, graph.edges, scene);
        const edgeMeshes = createEdges(graph.edges, nodeMeshes, scene);
        console.log(`Loaded ${graph.nodes.length} nodes, ${graph.edges.length} edges`);
    } catch (err) {
        console.error('Failed to load graph:', err);
    }
}

init();
animate(renderer, scene, camera, controls);
