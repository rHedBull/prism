import * as THREE from 'three';
import { highlightEdges, resetEdgeHighlights } from './edges.js';

const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

export function setupInteraction(camera, scene, nodeDataMap, edgeMeshes, nodeMeshes) {
    const infoPanel = document.getElementById('info-panel');
    let hoveredMesh = null;
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
