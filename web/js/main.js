import * as THREE from 'three';
import { createScene, animate, animateCamera } from './scene.js';
import { loadGraph, groupByAbstractionLevel } from './graph-loader.js';
import { createLayers, LAYER_SIZE } from './layers.js';
import { createEdges } from './edges.js';
import { setupInteraction } from './interaction.js';

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
        const edgeMeshes = createEdges(graph.edges, nodeMeshes, scene, graph.nodes);

        // Build parent map for call edge hover resolution
        const parentMap = {};
        for (const node of graph.nodes) {
            if (node.parent) parentMap[node.id] = node.parent;
        }

        setupInteraction(camera, scene, nodeDataMap, edgeMeshes, nodeMeshes, layerMeshes, controls, animateCamera, defaultCameraPos, defaultTarget, LAYER_SIZE, parentMap);
        console.log(`Loaded ${graph.nodes.length} nodes, ${graph.edges.length} edges`);
    } catch (err) {
        console.error('Failed to load graph:', err);
    }
}

init();
animate(renderer, scene, camera, controls);
