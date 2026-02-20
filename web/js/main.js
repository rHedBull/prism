import * as THREE from 'three';
import { createScene, animate, animateCamera, panelState } from './scene.js';
import { loadGraph, groupByAbstractionLevel } from './graph-loader.js';
import { createLayers, LAYER_SIZE } from './layers.js';
import { createEdges } from './edges.js';
import { setupInteraction } from './interaction.js';
import { createTreePanel } from './tree-panel.js';
import { initConfigPanel } from './config-panel.js';

const { scene, camera, renderer, controls, resizeCanvas } = createScene();

const defaultCameraPos = new THREE.Vector3(45, 50, 45);
const defaultTarget = new THREE.Vector3(0, 15, 0);

camera.position.copy(defaultCameraPos);
controls.target.copy(defaultTarget);

document.getElementById('btn-reset').addEventListener('click', () => {
    animateCamera(camera, controls, defaultCameraPos, defaultTarget);
});

// Panel collapse toggles
function setupPanelToggles() {
    const treePanel = document.getElementById('tree-panel');
    const configPanel = document.getElementById('config-panel');
    const toggleLeft = document.getElementById('toggle-left');
    const toggleRight = document.getElementById('toggle-right');
    const controlsEl = document.getElementById('controls');

    function updateControlsPosition() {
        const leftOffset = panelState.left ? 280 : 0;
        controlsEl.style.left = `${leftOffset + 16}px`;
    }

    toggleLeft.addEventListener('click', () => {
        panelState.left = !panelState.left;
        treePanel.classList.toggle('collapsed', !panelState.left);
        toggleLeft.classList.toggle('panel-closed', !panelState.left);
        toggleLeft.textContent = panelState.left ? '\u25C2' : '\u25B8';
        updateControlsPosition();
        resizeCanvas();
    });

    toggleRight.addEventListener('click', () => {
        panelState.right = !panelState.right;
        configPanel.classList.toggle('collapsed', !panelState.right);
        toggleRight.classList.toggle('panel-closed', !panelState.right);
        toggleRight.textContent = panelState.right ? '\u25B8' : '\u25C2';
        resizeCanvas();
    });

    updateControlsPosition();
}

setupPanelToggles();

async function init() {
    try {
        const graph = await loadGraph('.');
        const layerGroups = groupByAbstractionLevel(graph.nodes);
        const { layerMeshes, nodeMeshes, nodeDataMap } = createLayers(layerGroups, graph.edges, scene);
        const edgeMeshes = createEdges(graph.edges, nodeMeshes, scene, graph.nodes);

        // Build parent map for call edge hover resolution
        const parentMap = {};
        for (const node of graph.nodes) {
            if (node.parent) parentMap[node.id] = node.parent;
        }

        setupInteraction(camera, scene, nodeDataMap, edgeMeshes, nodeMeshes, layerMeshes, controls, animateCamera, defaultCameraPos, defaultTarget, LAYER_SIZE, parentMap);

        const treePanel = createTreePanel(graph, layerGroups, nodeMeshes, camera, controls, animateCamera);

        // Wire up graph hover -> tree selection sync
        window._graphHoverCallback = (nodeId) => {
            if (nodeId) treePanel.selectNode(nodeId);
            else treePanel.clearSelection();
        };

        // Init config panel with mesh references
        initConfigPanel(graph, layerGroups, nodeMeshes, edgeMeshes, layerMeshes, nodeDataMap);

        console.log(`Loaded ${graph.nodes.length} nodes, ${graph.edges.length} edges`);
    } catch (err) {
        console.error('Failed to load graph:', err);
    }
}

init();
animate(renderer, scene, camera, controls);
