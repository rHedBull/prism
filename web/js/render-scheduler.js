/**
 * On-demand render scheduler.
 *
 * Decoupled from Three.js so it can be tested in Node.
 * Call `createRenderScheduler(callbacks)` with your render pipeline;
 * it returns a `requestRender` function that coalesces to at most
 * one `requestAnimationFrame` per frame.
 */

export function createRenderScheduler({ scheduleFrame, render, hasPendingWork }) {
    let requested = false;

    function requestRender() {
        if (requested) return;
        requested = true;
        scheduleFrame(() => {
            requested = false;
            render();
            if (hasPendingWork()) requestRender();
        });
    }

    return { requestRender, _isRequested: () => requested };
}
