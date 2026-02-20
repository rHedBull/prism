import * as THREE from 'three';
import { highlightEdges, resetEdgeHighlights } from './edges.js';
import { getLeftOffset, getCanvasWidth } from './scene.js';

const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

// Build id->mesh lookup for tree panel hover
let _idToMesh = null;
let _nodeDataMapRef = null;
let _edgeMeshesRef = null;
let _nodeMeshesRef = null;
let _parentMapRef = null;

export function setupInteraction(camera, scene, nodeDataMap, edgeMeshes, nodeMeshes, layerMeshes, controls, animateCameraFn, defaultCameraPos, defaultTarget, LAYER_SIZE, parentMap) {
    const infoPanel = document.getElementById('info-panel');
    let hoveredMesh = null;
    let focusedLayer = null;
    const spotlightLines = [];
    let hoverFromTree = false;

    _nodeDataMapRef = nodeDataMap;
    _edgeMeshesRef = edgeMeshes;
    _nodeMeshesRef = nodeMeshes;
    _parentMapRef = parentMap;

    // Build id -> mesh lookup
    _idToMesh = {};
    for (const [mesh, data] of nodeDataMap) {
        _idToMesh[data.id] = mesh;
    }

    // Build descendant map from _layerParent: parentId -> [childIds] (recursive)
    const childMap = {};
    for (const [, data] of nodeDataMap) {
        const pid = data._layerParent;
        if (pid) {
            if (!childMap[pid]) childMap[pid] = [];
            childMap[pid].push(data.id);
        }
    }

    function getDescendants(nodeId) {
        const result = new Set();
        const stack = [nodeId];
        while (stack.length > 0) {
            const id = stack.pop();
            const children = childMap[id] || [];
            for (const cid of children) {
                result.add(cid);
                stack.push(cid);
            }
        }
        return result;
    }

    function getAncestors(nodeId) {
        const result = new Set();
        const data = [...nodeDataMap.values()].find(d => d.id === nodeId);
        if (!data) return result;
        let pid = data._layerParent;
        while (pid) {
            result.add(pid);
            const parentData = [...nodeDataMap.values()].find(d => d.id === pid);
            pid = parentData ? parentData._layerParent : null;
        }
        return result;
    }

    function clearSpotlights() {
        for (const obj of spotlightLines) {
            scene.remove(obj);
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        }
        spotlightLines.length = 0;
    }

    function drawSpotlight(parentMesh, childMeshes, color) {
        for (const childMesh of childMeshes) {
            const start = parentMesh.position.clone();
            const end = childMesh.position.clone();
            // Vertical dashed line from parent down to child
            const points = [
                new THREE.Vector3(start.x, start.y - 0.5, start.z),
                new THREE.Vector3(end.x, end.y + 0.5, end.z),
            ];
            const geo = new THREE.BufferGeometry().setFromPoints(points);
            const mat = new THREE.LineDashedMaterial({
                color,
                transparent: true,
                opacity: 0.4,
                dashSize: 0.6,
                gapSize: 0.3,
            });
            const line = new THREE.Line(geo, mat);
            line.computeLineDistances();
            scene.add(line);
            spotlightLines.push(line);
        }
    }

    window.addEventListener('mousemove', (event) => {
        const leftOffset = getLeftOffset();
        const canvasWidth = getCanvasWidth();
        mouse.x = ((event.clientX - leftOffset) / canvasWidth) * 2 - 1;
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
                    clearSpotlights();
                }

                hoveredMesh = mesh;
                mesh.material.emissive.setHex(0x222222);

                hoverFromTree = false;
                const data = nodeDataMap.get(mesh);
                showInfoPanel(data);
                highlightEdges(edgeMeshes, data.id, parentMap);

                // Sync tree panel selection
                if (window._graphHoverCallback) window._graphHoverCallback(data.id);

                // Highlight descendants and ancestors
                const descendants = getDescendants(data.id);
                const ancestors = getAncestors(data.id);
                const family = new Set([data.id, ...descendants, ...ancestors]);

                // Fade unrelated nodes, highlight family
                for (const [id, m] of Object.entries(nodeMeshes)) {
                    if (family.has(id)) {
                        m.material.opacity = 1.0;
                        if (descendants.has(id)) {
                            m.material.emissiveIntensity = 0.5;
                        }
                    } else {
                        m.material.opacity = 0.08;
                    }
                }

                // Draw spotlight lines to direct children
                const directChildren = childMap[data.id] || [];
                const childMeshes = directChildren
                    .map(cid => nodeMeshes[cid])
                    .filter(Boolean);
                if (childMeshes.length > 0) {
                    const color = mesh.material.color.getHex();
                    drawSpotlight(mesh, childMeshes, color);
                }
            }
        } else if (hoveredMesh && !hoverFromTree) {
            hoveredMesh.material.emissiveIntensity = 0.15;
            hoveredMesh = null;
            infoPanel.style.display = 'none';
            resetEdgeHighlights(edgeMeshes);
            resetNodeOpacity(nodeMeshes);
            clearSpotlights();
            if (window._graphHoverCallback) window._graphHoverCallback(null);
        }
    });

    window.addEventListener('click', (event) => {
        raycaster.setFromCamera(mouse, camera);

        // Check layer planes
        const layerPlanes = Object.values(layerMeshes);
        const layerHits = raycaster.intersectObjects(layerPlanes, true);

        if (layerHits.length > 0) {
            const layer = layerHits[0].object;
            const level = layer.userData.level;
            const y = layer.position.y;

            if (focusedLayer === level) {
                focusedLayer = null;
                animateCameraFn(camera, controls, defaultCameraPos, defaultTarget);
            } else {
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

    // Tree panel hover: highlight a node by id (from panel hover)
    window._treePanelHoverCallback = (nodeId) => {
        const mesh = _idToMesh[nodeId];
        if (!mesh) return;

        // Reset previous
        if (hoveredMesh) {
            hoveredMesh.material.emissive.setHex(0x000000);
            resetEdgeHighlights(edgeMeshes);
            resetNodeOpacity(nodeMeshes);
            clearSpotlights();
        }

        hoverFromTree = true;
        hoveredMesh = mesh;
        mesh.material.emissive.setHex(0x222222);

        const data = nodeDataMap.get(mesh);
        showInfoPanel(data);
        highlightEdges(edgeMeshes, data.id, parentMap);

        const descendants = getDescendants(data.id);
        const ancestors = getAncestors(data.id);
        const family = new Set([data.id, ...descendants, ...ancestors]);

        for (const [id, m] of Object.entries(nodeMeshes)) {
            if (family.has(id)) {
                m.material.opacity = 1.0;
                if (descendants.has(id)) m.material.emissiveIntensity = 0.5;
            } else {
                m.material.opacity = 0.08;
            }
        }

        const directChildren = childMap[data.id] || [];
        const childMeshes = directChildren.map(cid => nodeMeshes[cid]).filter(Boolean);
        if (childMeshes.length > 0) {
            drawSpotlight(mesh, childMeshes, mesh.material.color.getHex());
        }
    };

    window._treePanelLeaveCallback = () => {
        if (hoveredMesh && hoverFromTree) {
            hoveredMesh.material.emissiveIntensity = 0.15;
            hoveredMesh = null;
            hoverFromTree = false;
            infoPanel.style.display = 'none';
            resetEdgeHighlights(edgeMeshes);
            resetNodeOpacity(nodeMeshes);
            clearSpotlights();
        }
    };
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

function resetNodeOpacity(nodeMeshes) {
    for (const [id, mesh] of Object.entries(nodeMeshes)) {
        mesh.material.opacity = 1.0;
        mesh.material.emissiveIntensity = 0.15;
    }
}
