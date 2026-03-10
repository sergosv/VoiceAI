import { StartNode } from './StartNode'
import { MessageNode } from './MessageNode'
import { CollectInputNode } from './CollectInputNode'
import { ConditionNode } from './ConditionNode'
import { ActionNode } from './ActionNode'
import { EndNode } from './EndNode'
import { TransferNode } from './TransferNode'
import { WaitNode } from './WaitNode'
import { LoopNode } from './LoopNode'
import { CollectMultipleNode } from './CollectMultipleNode'

// Definido FUERA de componentes para evitar re-renders de React Flow
export const nodeTypes = {
  start: StartNode,
  message: MessageNode,
  collectInput: CollectInputNode,
  condition: ConditionNode,
  action: ActionNode,
  end: EndNode,
  transfer: TransferNode,
  wait: WaitNode,
  loop: LoopNode,
  collectMultiple: CollectMultipleNode,
}
