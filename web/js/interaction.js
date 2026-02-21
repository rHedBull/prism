import * as THREE from 'three';
import { highlightEdges, resetEdgeHighlights } from './edges.js';
import { getLeftOffset, getCanvasWidth, requestRender } from './scene.js';
import { getDiffState, getDiffHoverInfo } from './diff-overlay.js';

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

    // Build id -> mesh and id -> data lookups
    _idToMesh = {};
    const _idToData = {};
    for (const [mesh, data] of nodeDataMap) {
        _idToMesh[data.id] = mesh;
        _idToData[data.id] = data;
    }

    // Pre-build mesh array once for raycasting (avoid allocation per mousemove)
    const _raycastMeshes = Array.from(nodeDataMap.keys());

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
                if (!result.has(cid)) {
                    result.add(cid);
                    stack.push(cid);
                }
            }
        }
        return result;
    }

    function getAncestors(nodeId) {
        const result = new Set();
        const data = _idToData[nodeId];
        if (!data) return result;
        let pid = data._layerParent;
        while (pid && !result.has(pid)) {
            result.add(pid);
            const parentData = _idToData[pid];
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

    function applyHoverHighlight(data) {
        const descendants = getDescendants(data.id);
        const ancestors = getAncestors(data.id);
        const family = new Set([data.id, ...descendants, ...ancestors]);

        for (const [id, m] of Object.entries(nodeMeshes)) {
            if (family.has(id)) {
                m.material.color.setHex(m.userData._origColor);
                m.material.emissiveIntensity = descendants.has(id) ? 0.5 : 0.15;
            } else {
                m.material.color.setHex(0xd8d6dc);
                m.material.emissiveIntensity = 0.0;
            }
        }

        const directChildren = childMap[data.id] || [];
        const childMeshes = directChildren.map(cid => nodeMeshes[cid]).filter(Boolean);
        if (childMeshes.length > 0) {
            drawSpotlight(data.id === data.id ? _idToMesh[data.id] : null, childMeshes, _idToMesh[data.id].material.color.getHex());
        }
    }

    let _mouseMoveQueued = false;
    window.addEventListener('mousemove', (event) => {
        mouse.x = ((event.clientX - getLeftOffset()) / getCanvasWidth()) * 2 - 1;
        mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

        if (_mouseMoveQueued) return;
        _mouseMoveQueued = true;
        requestAnimationFrame(() => {
        _mouseMoveQueued = false;

        raycaster.setFromCamera(mouse, camera);
        const intersects = raycaster.intersectObjects(_raycastMeshes);

        if (intersects.length > 0) {
            const mesh = intersects[0].object;
            if (mesh !== hoveredMesh) {
                if (hoveredMesh) {
                    if (hoveredMesh.material.emissive) hoveredMesh.material.emissive.setHex(0x000000);
                    resetEdgeHighlights(edgeMeshes);
                    resetNodeOpacity(nodeMeshes);
                    clearSpotlights();
                }

                hoveredMesh = mesh;
                if (mesh.material.emissive) mesh.material.emissive.setHex(0x222222);

                hoverFromTree = false;
                const data = nodeDataMap.get(mesh);
                showInfoPanel(data);
                highlightEdges(edgeMeshes, data.id, parentMap);

                if (window._graphHoverCallback) window._graphHoverCallback(data.id);

                const descendants = getDescendants(data.id);
                const ancestors = getAncestors(data.id);
                const family = new Set([data.id, ...descendants, ...ancestors]);

                const { diffActive: _da, addedIds: _ai, removedIds: _ri, modifiedIds: _mi, movedIds: _moi } = getDiffState();
                for (const [id, m] of Object.entries(nodeMeshes)) {
                    const isDiffNode = _da && (_ai.has(id) || _ri.has(id) || _mi.has(id) || _moi.has(id));
                    if (isDiffNode) continue; // don't touch diff-colored nodes
                    if (family.has(id)) {
                        m.material.color.setHex(m.userData._origColor);
                        m.material.emissiveIntensity = descendants.has(id) ? 0.5 : 0.15;
                        m.material.opacity = _da ? 0.6 : 1.0;
                    } else {
                        if (_da) {
                            m.material.opacity = 0.05;
                            m.material.emissiveIntensity = 0.0;
                        } else {
                            m.material.color.setHex(0xd8d6dc);
                            m.material.emissiveIntensity = 0.0;
                        }
                    }
                }

                const directChildren = childMap[data.id] || [];
                const childMeshes = directChildren
                    .map(cid => nodeMeshes[cid])
                    .filter(Boolean);
                if (childMeshes.length > 0) {
                    const color = mesh.material.color.getHex();
                    drawSpotlight(mesh, childMeshes, color);
                }
                requestRender();
            }
        } else if (hoveredMesh && !hoverFromTree) {
            if (hoveredMesh.material.emissiveIntensity !== undefined) hoveredMesh.material.emissiveIntensity = 0.15;
            hoveredMesh = null;
            infoPanel.style.display = 'none';
            resetEdgeHighlights(edgeMeshes);
            resetNodeOpacity(nodeMeshes);
            clearSpotlights();
            if (window._graphHoverCallback) window._graphHoverCallback(null);
            requestRender();
        }
        }); // end requestAnimationFrame
    }); // end mousemove

    window.addEventListener('click', (event) => {
        raycaster.setFromCamera(mouse, camera);

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

        if (hoveredMesh) {
            if (hoveredMesh.material.emissive) hoveredMesh.material.emissive.setHex(0x000000);
            resetEdgeHighlights(edgeMeshes);
            resetNodeOpacity(nodeMeshes);
            clearSpotlights();
        }

        hoverFromTree = true;
        hoveredMesh = mesh;
        if (mesh.material.emissive) mesh.material.emissive.setHex(0x222222);

        const data = nodeDataMap.get(mesh);
        showInfoPanel(data);
        highlightEdges(edgeMeshes, data.id, parentMap);

        const descendants = getDescendants(data.id);
        const ancestors = getAncestors(data.id);
        const family = new Set([data.id, ...descendants, ...ancestors]);

        const { diffActive: _da2, addedIds: _ai2, removedIds: _ri2, modifiedIds: _mi2, movedIds: _moi2 } = getDiffState();
        for (const [id, m] of Object.entries(nodeMeshes)) {
            const isDiffNode = _da2 && (_ai2.has(id) || _ri2.has(id) || _mi2.has(id) || _moi2.has(id));
            if (isDiffNode) continue;
            if (family.has(id)) {
                m.material.color.setHex(m.userData._origColor);
                m.material.emissiveIntensity = descendants.has(id) ? 0.5 : 0.15;
                m.material.opacity = _da2 ? 0.6 : 1.0;
            } else {
                if (_da2) {
                    m.material.opacity = 0.05;
                    m.material.emissiveIntensity = 0.0;
                } else {
                    m.material.color.setHex(0xd8d6dc);
                    m.material.emissiveIntensity = 0.0;
                }
            }
        }

        const directChildren = childMap[data.id] || [];
        const childMeshes = directChildren.map(cid => nodeMeshes[cid]).filter(Boolean);
        if (childMeshes.length > 0) {
            drawSpotlight(mesh, childMeshes, mesh.material.color.getHex());
        }
        requestRender();
    };

    window._treePanelLeaveCallback = () => {
        if (hoveredMesh && hoverFromTree) {
            if (hoveredMesh.material.emissiveIntensity !== undefined) hoveredMesh.material.emissiveIntensity = 0.15;
            hoveredMesh = null;
            hoverFromTree = false;
            infoPanel.style.display = 'none';
            resetEdgeHighlights(edgeMeshes);
            resetNodeOpacity(nodeMeshes);
            clearSpotlights();
            requestRender();
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

    const diffDetails = document.getElementById('info-diff-details');
    const { diffActive, diffData } = getDiffState();
    if (diffActive && diffData) {
        const lines = getDiffHoverInfo(data.id, diffData);
        if (lines && lines.length > 0) {
            diffDetails.textContent = '';
            for (const line of lines) {
                const div = document.createElement('div');
                div.textContent = line;
                if (line.startsWith('+')) div.style.color = '#4CAF50';
                else if (line.startsWith('-')) div.style.color = '#F44336';
                else div.style.color = '#FFC107';
                diffDetails.appendChild(div);
            }
            diffDetails.style.display = 'block';
        } else {
            diffDetails.style.display = 'none';
        }
    } else {
        diffDetails.style.display = 'none';
    }

    panel.style.display = 'block';
}

function resetNodeOpacity(nodeMeshes) {
    const { diffActive, addedIds, removedIds, modifiedIds, movedIds } = getDiffState();
    for (const [id, mesh] of Object.entries(nodeMeshes)) {
        if (diffActive) {
            const isChanged = addedIds.has(id) || removedIds.has(id) || modifiedIds.has(id) || movedIds.has(id);
            if (isChanged) {
                // Don't touch diff-colored nodes — they use BasicMaterial
                continue;
            } else {
                mesh.material.opacity = 0.08;
                mesh.material.emissiveIntensity = 0.02;
            }
        } else {
            mesh.material.color.setHex(mesh.userData._origColor);
            mesh.material.emissiveIntensity = 0.15;
        }
    }
}
