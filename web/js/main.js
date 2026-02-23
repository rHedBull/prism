import * as THREE from 'three';
import { createScene, initRenderer, animateCamera, requestRender, panelState } from './scene.js';
import { loadGraph, groupByAbstractionLevel } from './graph-loader.js';
import { createLayers, LAYER_SIZE } from './layers.js';
import { createEdges } from './edges.js';
import { createSemanticEdges, updateSemanticEdgeVisibility } from './semantic-edges.js';
import { createNodeIcons, updateIconVisibility } from './node-icons.js';
import { setupInteraction } from './interaction.js';
import { createTreePanel } from './tree-panel.js';
import { initConfigPanel } from './config-panel.js';
import { activateDiffMode, deactivateDiffMode, loadDiff } from './diff-overlay.js';
import { create2DCamera, build2DScene, destroy2DScene, setup2DControls, resize2DCamera } from './mode-2d.js';

const { scene, camera, renderer, controls, resizeCanvas } = createScene();
window._viewMode = '3d';
window._activeCamera = camera;

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
        const diffSummary = document.getElementById('diff-summary');
        if (diffSummary) diffSummary.style.left = `${leftOffset + 16}px`;
    }

    toggleLeft.addEventListener('click', () => {
        panelState.left = !panelState.left;
        treePanel.classList.toggle('collapsed', !panelState.left);
        toggleLeft.classList.toggle('panel-closed', !panelState.left);
        toggleLeft.textContent = panelState.left ? '\u25C2' : '\u25B8';
        updateControlsPosition();
        resizeCanvas();
        requestRender();
    });

    toggleRight.addEventListener('click', () => {
        panelState.right = !panelState.right;
        configPanel.classList.toggle('collapsed', !panelState.right);
        toggleRight.classList.toggle('panel-closed', !panelState.right);
        toggleRight.textContent = panelState.right ? '\u25B8' : '\u25C2';
        resizeCanvas();
        requestRender();
    });

    updateControlsPosition();
}

setupPanelToggles();

async function init() {
    try {
        const graph = await loadGraph('.');
        const layerGroups = groupByAbstractionLevel(graph.nodes, graph.edges);
        const { layerMeshes, nodeMeshes, nodeDataMap } = await createLayers(layerGroups, graph.edges, scene);
        const edgeMeshes = createEdges(graph.edges, nodeMeshes, scene, graph.nodes);

        // Semantic edges and node icons (from optional semantic.json)
        let semanticEdgeGroups = [];
        let iconSprites = [];
        if (graph.semantic) {
            semanticEdgeGroups = createSemanticEdges(graph.semantic, nodeMeshes, scene);
            iconSprites = createNodeIcons(graph.semantic, nodeMeshes, scene);
        }

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
        initConfigPanel(graph, layerGroups, nodeMeshes, edgeMeshes, layerMeshes, nodeDataMap, semanticEdgeGroups, iconSprites);

        // Check for diff.json and set up toggle
        const diff = await loadDiff('.');
        let diffShown = false;
        if (diff) {
            activateDiffMode(diff, nodeMeshes, edgeMeshes, scene);
            diffShown = true;
            treePanel.refresh();
            requestRender();
        }

        // Wire up Diff toggle button
        document.getElementById('btn-toggle-diff').addEventListener('click', () => {
            if (!diff) return;
            if (diffShown) {
                deactivateDiffMode(nodeMeshes, edgeMeshes, scene);
                diffShown = false;
            } else {
                activateDiffMode(diff, nodeMeshes, edgeMeshes, scene);
                diffShown = true;
            }
            treePanel.refresh();
            requestRender();
        });

        // Create 2D camera and controls
        const camera2d = create2DCamera();
        setup2DControls(renderer);
        window._resize2DCamera = resize2DCamera;

        // 2D/3D mode toggle
        const toggleBtn = document.getElementById('btn-toggle-2d');
        toggleBtn.addEventListener('click', () => {
            if (window._viewMode === '3d') {
                window._viewMode = '2d';
                toggleBtn.textContent = '3D View';

                // Hide all 3D objects
                for (const group of Object.values(layerMeshes)) group.visible = false;
                for (const mesh of Object.values(nodeMeshes)) mesh.visible = false;
                for (const line of edgeMeshes) line.visible = false;
                // Hide semantic edges and icons in 2D mode
                for (const group of semanticEdgeGroups) group.visible = false;
                for (const sprite of iconSprites) sprite.visible = false;

                // Build 2D scene
                build2DScene(layerGroups, scene);
                controls.enabled = false;
                window._activeCamera = camera2d;

                // Hide layer toggles in config panel
                const layersSection = document.getElementById('layer-3')?.closest('.config-section');
                if (layersSection) layersSection.style.display = 'none';

                requestRender();
            } else {
                window._viewMode = '3d';
                toggleBtn.textContent = '2D View';

                // Destroy 2D scene
                destroy2DScene(scene);

                // Restore 3D objects
                for (const group of Object.values(layerMeshes)) group.visible = true;
                for (const [id, mesh] of Object.entries(nodeMeshes)) mesh.visible = true;
                for (const line of edgeMeshes) line.visible = true;
                // Restore semantic edges and icons (visibility will be synced by config panel)
                updateSemanticEdgeVisibility(semanticEdgeGroups, nodeMeshes);
                updateIconVisibility(iconSprites, nodeMeshes);

                controls.enabled = true;
                window._activeCamera = camera;

                // Show layer toggles again
                const layersSection = document.getElementById('layer-3')?.closest('.config-section');
                if (layersSection) layersSection.style.display = '';

                requestRender();
            }
        });

        requestRender();
        console.log(`Loaded ${graph.nodes.length} nodes, ${graph.edges.length} edges`);
    } catch (err) {
        console.error('Failed to load graph:', err);
    }
}

initRenderer(renderer, scene, camera, controls);
init();
