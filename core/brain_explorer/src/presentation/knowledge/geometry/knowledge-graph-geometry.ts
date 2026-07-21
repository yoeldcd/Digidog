/**
 * Calculate the shortest Euclidean distance between a point and a finite segment.
 * Degenerate segments are treated as a single endpoint so callers never divide by
 * zero. The function is coordinate-system agnostic and has no canvas dependency.
 *
 * @param {number} pointX Horizontal coordinate of the tested point.
 * @param {number} pointY Vertical coordinate of the tested point.
 * @param {number} startX Horizontal coordinate of the segment start.
 * @param {number} startY Vertical coordinate of the segment start.
 * @param {number} endX Horizontal coordinate of the segment end.
 * @param {number} endY Vertical coordinate of the segment end.
 * @returns {number} Shortest distance in the same units as the supplied coordinates.
 */
export function pointToSegmentDistance(
    pointX: number,
    pointY: number,
    startX: number,
    startY: number,
    endX: number,
    endY: number,
): number {
    const deltaX = endX - startX;
    const deltaY = endY - startY;
    if (deltaX === 0 && deltaY === 0) return Math.hypot(pointX - startX, pointY - startY);
    const projection = (((pointX - startX) * deltaX) + ((pointY - startY) * deltaY))
        / ((deltaX * deltaX) + (deltaY * deltaY));
    const ratio = Math.max(0, Math.min(1, projection));
    return Math.hypot(pointX - (startX + ratio * deltaX), pointY - (startY + ratio * deltaY));
}
