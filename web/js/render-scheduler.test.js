import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { createRenderScheduler } from './render-scheduler.js';

describe('render-scheduler', () => {
    let renderCount;
    let scheduledCallbacks;
    let pendingWork;
    let scheduler;

    function makeScheduler() {
        renderCount = 0;
        scheduledCallbacks = [];
        pendingWork = false;
        scheduler = createRenderScheduler({
            scheduleFrame: (cb) => scheduledCallbacks.push(cb),
            render: () => { renderCount++; },
            hasPendingWork: () => pendingWork,
        });
    }

    /** Flush exactly one scheduled frame callback. */
    function flushOne() {
        assert.ok(scheduledCallbacks.length > 0, 'expected a scheduled callback');
        const cb = scheduledCallbacks.shift();
        cb();
    }

    beforeEach(makeScheduler);

    it('does not render until frame fires', () => {
        scheduler.requestRender();
        assert.equal(renderCount, 0);
        assert.equal(scheduledCallbacks.length, 1);
    });

    it('renders exactly once per frame', () => {
        scheduler.requestRender();
        flushOne();
        assert.equal(renderCount, 1);
        assert.equal(scheduledCallbacks.length, 0, 'no more frames scheduled');
    });

    it('coalesces multiple requestRender calls into one frame', () => {
        scheduler.requestRender();
        scheduler.requestRender();
        scheduler.requestRender();
        assert.equal(scheduledCallbacks.length, 1, 'only one frame scheduled');
        flushOne();
        assert.equal(renderCount, 1);
    });

    it('allows new request after frame completes', () => {
        scheduler.requestRender();
        flushOne();
        assert.equal(renderCount, 1);

        scheduler.requestRender();
        assert.equal(scheduledCallbacks.length, 1);
        flushOne();
        assert.equal(renderCount, 2);
    });

    it('continues rendering while hasPendingWork returns true', () => {
        pendingWork = true;
        scheduler.requestRender();

        // Flush 3 frames with pending work
        for (let i = 0; i < 3; i++) {
            flushOne();
        }
        assert.equal(renderCount, 3);
        assert.equal(scheduledCallbacks.length, 1, 'still scheduling');

        // Stop pending work
        pendingWork = false;
        flushOne();
        assert.equal(renderCount, 4);
        assert.equal(scheduledCallbacks.length, 0, 'stopped scheduling');
    });

    it('does NOT schedule infinite frames when idle', () => {
        scheduler.requestRender();
        flushOne();
        // After one render with no pending work, no more frames
        assert.equal(scheduledCallbacks.length, 0);
        assert.equal(renderCount, 1);
    });

    it('caps render count: 1000 flushes with no pending work = 1 render', () => {
        // Simulates what would happen if there were an infinite loop bug:
        // each flush should NOT schedule another frame when idle.
        scheduler.requestRender();
        flushOne();

        // After the single render, no more callbacks should exist
        let extraRenders = 0;
        for (let i = 0; i < 1000; i++) {
            if (scheduledCallbacks.length === 0) break;
            flushOne();
            extraRenders++;
        }
        assert.equal(extraRenders, 0, 'no extra renders when idle');
        assert.equal(renderCount, 1);
    });

    it('caps render count: 100 flushes with pending work = exactly 100 renders', () => {
        // Verify that pending work causes exactly 1 render per flush (no runaway)
        pendingWork = true;
        scheduler.requestRender();
        for (let i = 0; i < 100; i++) {
            flushOne();
        }
        assert.equal(renderCount, 100, 'exactly one render per frame');
        assert.equal(scheduledCallbacks.length, 1, 'one pending');
    });

    it('BUG REGRESSION: change event during render does not cause infinite loop', () => {
        // Simulates OrbitControls.update() firing "change" during render.
        // The old code had controls.update() inside the rAF callback, which
        // fired "change" -> requestRender() -> new rAF -> repeat forever.
        //
        // With the scheduler, even if requestRender is called during render(),
        // it should schedule at most one additional frame, not infinite.
        let reentrantCallCount = 0;
        const reentrantScheduler = createRenderScheduler({
            scheduleFrame: (cb) => scheduledCallbacks.push(cb),
            render: () => {
                renderCount++;
                // Simulate: render triggers a "change" event that calls requestRender
                reentrantCallCount++;
                if (reentrantCallCount <= 100) {
                    reentrantScheduler.requestRender();
                }
            },
            hasPendingWork: () => false,
        });

        reentrantScheduler.requestRender();

        // Flush frames — should converge, not explode
        let totalFrames = 0;
        while (scheduledCallbacks.length > 0 && totalFrames < 300) {
            flushOne();
            totalFrames++;
        }

        // Key assertion: re-entrant requestRender during render causes at most
        // 2 frames per cycle (current frame + one scheduled by re-entry).
        // With 100 re-entries capped, we expect ~101 renders, not infinite.
        assert.ok(totalFrames <= 105, `expected bounded frames, got ${totalFrames}`);
        assert.equal(scheduledCallbacks.length, 0, 'eventually stops');
    });
});
