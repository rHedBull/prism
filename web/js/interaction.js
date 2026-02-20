import * as THREE from 'three';
import { highlightEdges, resetEdgeHighlights } from './edges.js';

const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

export function setupInteraction(camera, scene, nodeDataMap, edgeMeshes, nodeMeshes, layerMeshes, controls, animateCameraFn, defaultCameraPos, defaultTarget, LAYER_SIZE) {
    const infoPanel = document.getElementById('info-panel');
    let hoveredMesh = null;
    let focusedLayer = null;
    const originalColors = new Map();

    window.addEventListener('mousemove', (event) => {
        mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);
        const meshes = Array.from(nodeDataMap.keys());
        const intersects = raycaster.intersectObjects(meshes);

        if (intersects.length > 0) {
            const mesh = intersects[0].object;
            if (mesh !== hoveredMesh) {
                // Reset previous
                if (hoveredMesh) {
                    hoveredMesh.material.emissive.setHex(0x000000);
                    resetEdgeHighlights(edgeMeshes);
                    resetNodeOpacity(nodeMeshes);
                }

                hoveredMesh = mesh;
                originalColors.set(mesh, mesh.material.color.getHex());
                mesh.material.emissive.setHex(0x333333);

                const data = nodeDataMap.get(mesh);
                showInfoPanel(data);
                highlightEdges(edgeMeshes, data.id);
                fadeUnconnectedNodes(nodeMeshes, edgeMeshes, data.id);
            }
        } else if (hoveredMesh) {
            hoveredMesh.material.emissive.setHex(0x000000);
            hoveredMesh = null;
            infoPanel.style.display = 'none';
            resetEdgeHighlights(edgeMeshes);
            resetNodeOpacity(nodeMeshes);
        }
    });

    window.addEventListener('click', (event) => {
        raycaster.setFromCamera(mouse, camera);

        // Check layer planes
        const layerPlanes = Object.values(layerMeshes);
        const layerHits = raycaster.intersectObjects(layerPlanes);

        if (layerHits.length > 0) {
            const layer = layerHits[0].object;
            const level = layer.userData.level;
            const y = layer.position.y;

            if (focusedLayer === level) {
                // Unfocus — back to vertical view
                focusedLayer = null;
                animateCameraFn(camera, controls, defaultCameraPos, defaultTarget);
            } else {
                // Focus this layer — horizontal view
                focusedLayer = level;
                const targetPos = new THREE.Vector3(LAYER_SIZE * 0.7, y + 5, LAYER_SIZE * 0.7);
                const targetLookAt = new THREE.Vector3(0, y, 0);
                animateCameraFn(camera, controls, targetPos, targetLookAt);
            }
            return;
        }
    });

    window.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && focusedLayer !== null) {
            focusedLayer = null;
            animateCameraFn(camera, controls, defaultCameraPos, defaultTarget);
        }
    });
}

function showInfoPanel(data) {
    const panel = document.getElementById('info-panel');
    document.getElementById('info-name').textContent = data.name;
    document.getElementById('info-type').textContent = data.type;
    document.getElementById('info-loc').textContent = data.lines_of_code;
    document.getElementById('info-lang').textContent = data.language || '—';
    document.getElementById('info-path').textContent = data.file_path;
    panel.style.display = 'block';
}

function fadeUnconnectedNodes(nodeMeshes, edgeMeshes, nodeId) {
    const connected = new Set([nodeId]);
    for (const line of edgeMeshes) {
        const edge = line.userData.edgeData;
        if (edge.from === nodeId) connected.add(edge.to);
        if (edge.to === nodeId) connected.add(edge.from);
    }
    for (const [id, mesh] of Object.entries(nodeMeshes)) {
        mesh.material.opacity = connected.has(id) ? 1.0 : 0.15;
        mesh.material.transparent = true;
    }
}

function resetNodeOpacity(nodeMeshes) {
    for (const mesh of Object.values(nodeMeshes)) {
        mesh.material.opacity = 1.0;
    }
}
