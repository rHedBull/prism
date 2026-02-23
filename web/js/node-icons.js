import * as THREE from 'three';

const ICON_SIZE = 64;
const SPRITE_SCALE = 2.5;

const ICON_DRAWERS = {
    database: drawDatabaseIcon,
    api: drawApiIcon,
    auth: drawAuthIcon,
    ui: drawUiIcon,
    service: drawServiceIcon,
    config: drawConfigIcon,
    model: drawModelIcon,
    core: drawCoreIcon,
    util: drawUtilIcon,
    test: drawTestIcon,
};

/**
 * Create icon sprites above C3/C2 nodes based on semantic categories.
 * Returns array of sprites added to the scene.
 */
export function createNodeIcons(semanticData, nodeMeshes, scene) {
    if (!semanticData || !semanticData.node_categories) return [];

    const sprites = [];
    const textureCache = {};

    for (const [nodeId, category] of Object.entries(semanticData.node_categories)) {
        const mesh = nodeMeshes[nodeId];
        if (!mesh) continue;

        const drawer = ICON_DRAWERS[category];
        if (!drawer) continue;

        // Cache textures per category
        if (!textureCache[category]) {
            textureCache[category] = createIconTexture(drawer);
        }

        const mat = new THREE.SpriteMaterial({
            map: textureCache[category],
            transparent: true,
            depthWrite: false,
        });
        const sprite = new THREE.Sprite(mat);

        // Position above the node
        const nodeHeight = mesh.geometry?.parameters?.height || 1;
        sprite.position.copy(mesh.position);
        sprite.position.y += nodeHeight / 2 + 1.5;

        sprite.scale.set(SPRITE_SCALE, SPRITE_SCALE, 1);
        sprite.userData = { type: 'node-icon', nodeId, category };

        scene.add(sprite);
        sprites.push(sprite);
    }

    return sprites;
}

function createIconTexture(drawFn) {
    const canvas = document.createElement('canvas');
    canvas.width = ICON_SIZE;
    canvas.height = ICON_SIZE;
    const ctx = canvas.getContext('2d');

    // Circular background
    ctx.fillStyle = 'rgba(248, 246, 252, 0.8)';
    ctx.beginPath();
    ctx.arc(ICON_SIZE / 2, ICON_SIZE / 2, ICON_SIZE / 2 - 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = 'rgba(140, 96, 243, 0.4)';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw the icon
    ctx.fillStyle = '#353148';
    ctx.strokeStyle = '#353148';
    ctx.lineWidth = 2;
    drawFn(ctx, ICON_SIZE);

    const texture = new THREE.CanvasTexture(canvas);
    texture.premultiplyAlpha = true;
    return texture;
}

// --- Icon draw functions ---
// All draw within a centered area of the ICON_SIZE canvas

function drawDatabaseIcon(ctx, s) {
    // Classic cylinder: top ellipse, body, bottom ellipse
    const cx = s / 2, cy = s / 2;
    const w = s * 0.35, h = s * 0.3;
    const ry = h * 0.3; // ellipse vertical radius

    ctx.beginPath();
    // Top ellipse
    ctx.ellipse(cx, cy - h / 2, w, ry, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Body sides
    ctx.beginPath();
    ctx.moveTo(cx - w, cy - h / 2);
    ctx.lineTo(cx - w, cy + h / 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx + w, cy - h / 2);
    ctx.lineTo(cx + w, cy + h / 2);
    ctx.stroke();

    // Bottom ellipse
    ctx.beginPath();
    ctx.ellipse(cx, cy + h / 2, w, ry, 0, 0, Math.PI);
    ctx.stroke();

    // Fill body
    ctx.fillStyle = 'rgba(53, 49, 72, 0.15)';
    ctx.fillRect(cx - w, cy - h / 2, w * 2, h);
}

function drawAuthIcon(ctx, s) {
    // Shield shape
    const cx = s / 2, top = s * 0.18, bottom = s * 0.82;
    const halfW = s * 0.3;
    ctx.beginPath();
    ctx.moveTo(cx, top);
    ctx.lineTo(cx + halfW, top + s * 0.12);
    ctx.lineTo(cx + halfW, s * 0.55);
    ctx.quadraticCurveTo(cx, bottom, cx, bottom);
    ctx.quadraticCurveTo(cx, bottom, cx - halfW, s * 0.55);
    ctx.lineTo(cx - halfW, top + s * 0.12);
    ctx.closePath();
    ctx.fillStyle = 'rgba(53, 49, 72, 0.2)';
    ctx.fill();
    ctx.strokeStyle = '#353148';
    ctx.stroke();
}

function drawApiIcon(ctx, s) {
    // Cloud with bidirectional arrows
    const cx = s / 2, cy = s * 0.4;
    // Simple cloud shape
    ctx.beginPath();
    ctx.arc(cx - s * 0.1, cy, s * 0.15, 0, Math.PI * 2);
    ctx.arc(cx + s * 0.1, cy, s * 0.15, 0, Math.PI * 2);
    ctx.arc(cx, cy - s * 0.08, s * 0.15, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(53, 49, 72, 0.15)';
    ctx.fill();
    ctx.strokeStyle = '#353148';
    ctx.stroke();
    // Arrows below
    const ay = s * 0.65;
    ctx.beginPath();
    ctx.moveTo(cx - s * 0.15, ay);
    ctx.lineTo(cx + s * 0.15, ay);
    ctx.moveTo(cx + s * 0.08, ay - 4);
    ctx.lineTo(cx + s * 0.15, ay);
    ctx.lineTo(cx + s * 0.08, ay + 4);
    ctx.stroke();
}

function drawUiIcon(ctx, s) {
    // Browser window
    const x = s * 0.2, y = s * 0.22, w = s * 0.6, h = s * 0.56;
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = 'rgba(53, 49, 72, 0.1)';
    ctx.fillRect(x, y, w, h);
    // Title bar
    ctx.beginPath();
    ctx.moveTo(x, y + h * 0.2);
    ctx.lineTo(x + w, y + h * 0.2);
    ctx.stroke();
    // Dots
    const dotY = y + h * 0.1;
    for (let i = 0; i < 3; i++) {
        ctx.beginPath();
        ctx.arc(x + 6 + i * 6, dotY, 2, 0, Math.PI * 2);
        ctx.fill();
    }
}

function drawServiceIcon(ctx, s) {
    // Hexagon
    const cx = s / 2, cy = s / 2, r = s * 0.3;
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 2;
        const px = cx + r * Math.cos(angle);
        const py = cy + r * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(53, 49, 72, 0.15)';
    ctx.fill();
    ctx.stroke();
}

function drawConfigIcon(ctx, s) {
    // Wrench / gear simplified as a small gear
    const cx = s / 2, cy = s / 2, r = s * 0.25;
    const teeth = 6;
    ctx.beginPath();
    for (let i = 0; i < teeth * 2; i++) {
        const angle = (Math.PI / teeth) * i - Math.PI / 2;
        const tr = i % 2 === 0 ? r : r * 0.7;
        const px = cx + tr * Math.cos(angle);
        const py = cy + tr * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(53, 49, 72, 0.2)';
    ctx.fill();
    ctx.stroke();
    // Center hole
    ctx.beginPath();
    ctx.arc(cx, cy, r * 0.25, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(248, 246, 252, 0.9)';
    ctx.fill();
}

function drawModelIcon(ctx, s) {
    // Stacked rectangles (schema)
    const cx = s / 2, w = s * 0.4, h = s * 0.12;
    for (let i = 0; i < 3; i++) {
        const y = s * 0.25 + i * (h + 4);
        ctx.strokeRect(cx - w / 2, y, w, h);
        ctx.fillStyle = 'rgba(53, 49, 72, 0.1)';
        ctx.fillRect(cx - w / 2, y, w, h);
    }
}

function drawCoreIcon(ctx, s) {
    // Diamond
    const cx = s / 2, cy = s / 2, r = s * 0.28;
    ctx.beginPath();
    ctx.moveTo(cx, cy - r);
    ctx.lineTo(cx + r, cy);
    ctx.lineTo(cx, cy + r);
    ctx.lineTo(cx - r, cy);
    ctx.closePath();
    ctx.fillStyle = 'rgba(53, 49, 72, 0.2)';
    ctx.fill();
    ctx.stroke();
}

function drawUtilIcon(ctx, s) {
    // Toolbox: rectangle with handle
    const cx = s / 2, w = s * 0.5, h = s * 0.35;
    const y = s * 0.38;
    ctx.strokeRect(cx - w / 2, y, w, h);
    ctx.fillStyle = 'rgba(53, 49, 72, 0.1)';
    ctx.fillRect(cx - w / 2, y, w, h);
    // Handle
    ctx.beginPath();
    ctx.arc(cx, y, w * 0.25, Math.PI, 0);
    ctx.stroke();
}

function drawTestIcon(ctx, s) {
    // Checkmark in a circle
    const cx = s / 2, cy = s / 2, r = s * 0.28;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(53, 49, 72, 0.1)';
    ctx.fill();
    ctx.stroke();
    // Checkmark
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(cx - r * 0.4, cy);
    ctx.lineTo(cx - r * 0.1, cy + r * 0.35);
    ctx.lineTo(cx + r * 0.4, cy - r * 0.3);
    ctx.stroke();
    ctx.lineWidth = 2;
}

/**
 * Update icon visibility to match their parent node visibility.
 */
export function updateIconVisibility(iconSprites, nodeMeshes) {
    for (const sprite of iconSprites) {
        const mesh = nodeMeshes[sprite.userData.nodeId];
        sprite.visible = mesh ? mesh.visible : false;
    }
}
