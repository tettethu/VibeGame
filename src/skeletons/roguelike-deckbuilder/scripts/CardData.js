/**
 * Card definitions. Pure data module — no Node lifecycle.
 * Each card: { id, name, type, cost, desc, effect, value?, draw?, category, icon }
 *   effect values: 'damage', 'damage_x2', 'block', 'vuln_enemy',
 *                  'block_draw', 'draw', 'power_overclock', 'power_reflex_grid'
 *   category: 'offense' | 'defense' | 'utility'  (for UpgradeChoiceModule band color)
 *   icon: inline SVG string
 */

const SWORD_SVG = '<svg viewBox="0 0 16 16" fill="currentColor" shape-rendering="crispEdges"><path d="M8 1 L9 5 L14 6 L9 7 L8 15 L7 7 L2 6 L7 5Z"/></svg>'
const SHIELD_SVG = '<svg viewBox="0 0 16 16" fill="currentColor" shape-rendering="crispEdges"><path d="M8 2 L13 4 L13 9 Q13 13 8 15 Q3 13 3 9 L3 4Z"/></svg>'
const BOLT_SVG = '<svg viewBox="0 0 16 16" fill="currentColor" shape-rendering="crispEdges"><path d="M9 1 L5 9 L8 9 L7 15 L11 7 L8 7Z"/></svg>'

export const STARTER_DECK_TEMPLATE = [
  { id: 'strike',  name: 'STRIKE',  type: 'Attack', cost: 1, desc: 'Deal 6 damage.',             effect: 'damage',  value: 6,  category: 'offense', icon: SWORD_SVG },
  { id: 'strike',  name: 'STRIKE',  type: 'Attack', cost: 1, desc: 'Deal 6 damage.',             effect: 'damage',  value: 6,  category: 'offense', icon: SWORD_SVG },
  { id: 'strike',  name: 'STRIKE',  type: 'Attack', cost: 1, desc: 'Deal 6 damage.',             effect: 'damage',  value: 6,  category: 'offense', icon: SWORD_SVG },
  { id: 'strike',  name: 'STRIKE',  type: 'Attack', cost: 1, desc: 'Deal 6 damage.',             effect: 'damage',  value: 6,  category: 'offense', icon: SWORD_SVG },
  { id: 'deflect', name: 'DEFLECT', type: 'Skill',  cost: 1, desc: 'Gain 5 Block.',              effect: 'block',   value: 5,  category: 'defense', icon: SHIELD_SVG },
  { id: 'deflect', name: 'DEFLECT', type: 'Skill',  cost: 1, desc: 'Gain 5 Block.',              effect: 'block',   value: 5,  category: 'defense', icon: SHIELD_SVG },
  { id: 'deflect', name: 'DEFLECT', type: 'Skill',  cost: 1, desc: 'Gain 5 Block.',              effect: 'block',   value: 5,  category: 'defense', icon: SHIELD_SVG },
  { id: 'deflect', name: 'DEFLECT', type: 'Skill',  cost: 1, desc: 'Gain 5 Block.',              effect: 'block',   value: 5,  category: 'defense', icon: SHIELD_SVG },
  { id: 'bash',    name: 'BASH',    type: 'Attack', cost: 2, desc: 'Deal 8 damage. Apply 2 Vulnerable to enemy.', effect: 'bash', value: 8, vuln: 2, category: 'offense', icon: SWORD_SVG },
  { id: 'bash',    name: 'BASH',    type: 'Attack', cost: 2, desc: 'Deal 8 damage. Apply 2 Vulnerable to enemy.', effect: 'bash', value: 8, vuln: 2, category: 'offense', icon: SWORD_SVG },
]

export const REWARD_POOL = [
  { id: 'twin_strike',  name: 'TWIN STRIKE',  type: 'Attack', cost: 1, desc: 'Deal 5 damage twice.',                      effect: 'twin_strike',       value: 5,  category: 'offense', icon: SWORD_SVG },
  { id: 'heavy_blow',   name: 'HEAVY BLOW',   type: 'Attack', cost: 2, desc: 'Deal 20 damage.',                            effect: 'damage',            value: 20, category: 'offense', icon: SWORD_SVG },
  { id: 'overload',     name: 'OVERLOAD',     type: 'Attack', cost: 3, desc: 'Deal 36 damage.',                            effect: 'damage',            value: 36, category: 'offense', icon: SWORD_SVG },
  { id: 'scramble',     name: 'SCRAMBLE',     type: 'Skill',  cost: 1, desc: 'Apply 3 Vulnerable to enemy.',              effect: 'vuln_enemy',        value: 3,  category: 'offense', icon: SWORD_SVG },
  { id: 'iron_curtain', name: 'IRON CURTAIN', type: 'Skill',  cost: 2, desc: 'Gain 16 Block.',                             effect: 'block',             value: 16, category: 'defense', icon: SHIELD_SVG },
  { id: 'phase_shift',  name: 'PHASE SHIFT',  type: 'Skill',  cost: 1, desc: 'Gain 3 Block. Draw 1 card.',                effect: 'block_draw',        value: 3,  draw: 1, category: 'defense', icon: SHIELD_SVG },
  { id: 'neural_link',  name: 'NEURAL LINK',  type: 'Skill',  cost: 1, desc: 'Draw 2 cards.',                              effect: 'draw',              value: 2,  category: 'utility', icon: BOLT_SVG },
  { id: 'overclock',    name: 'OVERCLOCK',    type: 'Power',  cost: 2, desc: 'All Attack cards deal +3 damage permanently.', effect: 'power_overclock',   category: 'utility', icon: BOLT_SVG },
  { id: 'reflex_grid',  name: 'REFLEX GRID',  type: 'Power',  cost: 1, desc: 'Gain 3 Block at the start of each turn.',   effect: 'power_reflex_grid', category: 'defense', icon: SHIELD_SVG },
]

/** Tooltip text for status terms referenced in card descriptions. */
export const TOOLTIPS = {
  BLOCK:       'Prevents damage until next turn. Block is removed at the start of your next turn.',
  VULNERABLE:  'The target takes 50% more damage from Attacks. Decreases by 1 each round.',
  POWER:       'Permanent effect. Lasts for the rest of the run.',
}

/** Build a shuffled starter deck with unique UIDs per card instance. */
export function buildStarterDeck() {
  return shuffle(STARTER_DECK_TEMPLATE.map((c, i) => ({ ...c, uid: `starter_${i}_${Date.now()}` })))
}

/** Fisher-Yates shuffle, returns a new array. */
export function shuffle(arr) {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]]
  }
  return a
}
