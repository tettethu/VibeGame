import { Node } from '/engine/Node.js'

// Per-room upgrade flow
export default class LevelUpManager extends Node {
  ready() {
    this.tags = ['level_manager']
  }

  onUpgradeClosed() {
    const gm = this.findByTag('game_manager')[0]
    if (gm) gm.resumeFromUpgrade()
  }

  triggerRoomUpgrade() {
    const gm = this.findByTag('game_manager')[0]
    if (gm) gm.pauseForUpgrade()
    const ui = this.findByTag('upgrade_ui')[0]
    if (ui) ui.show()
  }
}
