/** Barrel export for vibegame engine */

export { Node, generateId } from './Node.js'
export { SceneTree } from './SceneTree.js'
export { PhaserHost } from './PhaserHost.js'
export { InputMap } from './InputMap.js'
export { VisualFactory } from './VisualFactory.js'
export { ColliderFactory } from './ColliderFactory.js'
export { RuntimeController } from './RuntimeController.js'
export { RuntimeBridge } from './RuntimeBridge.js'
export { AutoTile } from './utils/AutoTile.js'
export { Vlm } from './ai/Vlm.js'
export { Imagegen } from './ai/Imagegen.js'

// Engine scripts (loaded dynamically by SceneTree), not imported directly.
// Register via: sceneTree.scriptClasses['TileMap'] = (await import('/engine/scripts/TileMap.js')).default
// Register via: sceneTree.scriptClasses['MountPoint'] = (await import('/engine/scripts/MountPoint.js')).default
// Register via: sceneTree.scriptClasses['Collider'] = (await import('/engine/scripts/Collider.js')).default
