/**
 * Циклы графа импортов: компоненты сильной связности из двух и более модулей
 * (алгоритм Тарьяна, итеративно — рекурсия упирается в стек на больших деревьях).
 * Каждый цикл — отсортированный список модулей; список циклов тоже отсортирован.
 */
export function findCycles(graph: ReadonlyMap<string, readonly string[]>): string[][] {
  const order = new Map<string, number>();
  const lowLink = new Map<string, number>();
  const onStack = new Set<string>();
  const stack: string[] = [];
  const cycles: string[][] = [];
  let counter = 0;

  for (const root of graph.keys()) {
    if (order.has(root)) continue;
    const work: [string, number][] = [[root, 0]];
    while (work.length > 0) {
      const frame = work[work.length - 1];
      if (frame === undefined) break;
      const [node, next] = frame;
      if (next === 0) {
        order.set(node, counter);
        lowLink.set(node, counter);
        counter += 1;
        stack.push(node);
        onStack.add(node);
      }
      const targets = graph.get(node) ?? [];
      const target = targets[next];
      if (target !== undefined) {
        frame[1] = next + 1;
        if (!order.has(target)) work.push([target, 0]);
        else if (onStack.has(target)) lowLink.set(node, Math.min(low(lowLink, node), low(order, target)));
        continue;
      }
      work.pop();
      const parent = work[work.length - 1];
      if (parent !== undefined) lowLink.set(parent[0], Math.min(low(lowLink, parent[0]), low(lowLink, node)));
      if (low(lowLink, node) !== low(order, node)) continue;
      const component: string[] = [];
      for (let member = stack.pop(); member !== undefined; member = stack.pop()) {
        onStack.delete(member);
        component.push(member);
        if (member === node) break;
      }
      if (component.length > 1) cycles.push(component.toSorted());
    }
  }
  return cycles.toSorted((left, right) => (left[0] ?? "").localeCompare(right[0] ?? ""));
}

function low(values: ReadonlyMap<string, number>, node: string): number {
  const value = values.get(node);
  if (value === undefined) throw new Error(`Узел ${node} ещё не пронумерован`);
  return value;
}
