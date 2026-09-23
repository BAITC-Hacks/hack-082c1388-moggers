import { test, expect } from '@playwright/test';
import type { Core } from 'cytoscape';
import { clusterGraph, indexGraph, nodeGraph, NODE_LIMIT } from '../src/graph';
import type { Dataset, GraphNode, Route } from '../src/types';

const node = (gid: string, cluster_id = 0): GraphNode => ({
  gid,
  cluster_id,
  role: 'transit',
  role_score: 0.8,
  priority_score: 0.5,
  evidence: 'Признаки транзита, 2 перевода',
  depth: 1,
  is_seed: false,
  in_deg: 1,
  out_deg: 1,
  in_kzt: 100,
  out_kzt: 100,
  in_tx: 1,
  out_tx: 1,
  pass_through: 1,
  seed_sources: 1,
  betweenness: 0,
  reciprocal_partners: 0,
  min_cycle_len: 0,
  is_articulation: false,
  depth_truncated: false,
  flow_kzt: 200,
});
function example(): Dataset {
  return {
    schema_version: 1,
    summary: {
      n_nodes: 5,
      n_edges: 5,
      n_tx: 7,
      n_seed: 0,
      turnover_kzt: 230,
      period: ['2026-07-01', '2026-07-31'],
    },
    nodes: [node('a'), node('b'), node('c', 1), node('d', 2), node('orphan', 3)],
    edges: [
      { src: 'a', dst: 'b', sum_kzt: 100, n_tx: 1 },
      { src: 'a', dst: 'c', sum_kzt: 80, n_tx: 2 },
      { src: 'b', dst: 'c', sum_kzt: 20, n_tx: 1 },
      { src: 'c', dst: 'a', sum_kzt: 30, n_tx: 1 },
      { src: 'd', dst: 'a', sum_kzt: 10, n_tx: 2 },
    ],
    clusters: [0, 1, 2, 3].map((cluster_id) => ({
      cluster_id,
      n_nodes: cluster_id === 0 ? 2 : 1,
      n_seed: 0,
      sum_kzt_internal: cluster_id === 0 ? 100 : 0,
      top_gids: [],
      hypothesis: '',
    })),
    top_nodes: [],
    resilience: [],
    role_labels: { transit: 'Транзит' },
    role_styles: { transit: { color: '#888', shape: 'ellipse', size: 20 } },
  };
}
const route: Route = {
  section: 'graph',
  view: 'node',
  focus: 'a',
  gid: 'a',
  card: '',
  q: '',
  role: '',
  cluster: '',
  depth: '',
  seed: '',
  scope: 'hops1',
  direction: 'all',
  minAmount: '',
};

test('cluster flows preserve direction, sum, counts and exclude internal transfers', () => {
  const data = example();
  const index = indexGraph(data);
  expect(index.clusterEdges.find((e) => e.src === 'cluster:0' && e.dst === 'cluster:1')).toEqual({
    src: 'cluster:0',
    dst: 'cluster:1',
    sum_kzt: 100,
    n_tx: 3,
  });
  expect(
    index.clusterEdges.find((e) => e.src === 'cluster:1' && e.dst === 'cluster:0')?.sum_kzt,
  ).toBe(30);
  expect(index.clusterEdges.some((e) => e.src === e.dst)).toBe(false);
  expect(clusterGraph(data, index, 2).nodes).toHaveLength(2);
  expect(clusterGraph(data, index, 2).edges).toHaveLength(2);
  expect(clusterGraph(data, index, 2, '3').nodes.some((n) => n.clusterId === 3)).toBe(true);
});

test('node view groups incoming, outgoing and reciprocal peers without duplication', () => {
  const data = example(),
    index = indexGraph(data);
  const graph = nodeGraph(data, index, data.nodes, route);
  expect(graph.nodes.map((n) => n.id).sort()).toEqual(['a', 'b', 'c', 'd']);
  expect(graph.nodes.find((n) => n.id === 'd')!.x).toBeLessThan(0);
  expect(graph.nodes.find((n) => n.id === 'b')!.x).toBeGreaterThan(0);
  expect(graph.nodes.find((n) => n.id === 'c')!.x).toBe(0);
  expect(graph.edges).toHaveLength(4);
  const incoming = nodeGraph(data, index, data.nodes, { ...route, direction: 'in' });
  expect(incoming.edges.every((e) => e.dst === 'a')).toBe(true);
  const outgoing = nodeGraph(data, index, data.nodes, { ...route, direction: 'out' });
  expect(outgoing.edges.every((e) => e.src === 'a')).toBe(true);
  const filtered = nodeGraph(data, index, data.nodes, { ...route, minAmount: '90' });
  expect(filtered.nodes.map((n) => n.id).sort()).toEqual(['a', 'b']);
  expect(nodeGraph(data, index, [], route).nodes.map((n) => n.id)).toEqual(['a']);
});

test('progressive expansion preserves direct positions and caps large neighborhoods', () => {
  const data = example();
  for (let i = 0; i < 200; i++) {
    const gid = `peer-${i.toString().padStart(3, '0')}`;
    data.nodes.push(node(gid));
    data.edges.push({ src: 'a', dst: gid, sum_kzt: 1000 - i, n_tx: 1 });
  }
  const index = indexGraph(data),
    small = nodeGraph(data, index, data.nodes, route);
  expect(small.nodes.length).toBeLessThanOrEqual(21);
  const more = nodeGraph(data, index, data.nodes, route, 10, 20);
  for (const n of small.nodes)
    expect(more.nodes.find((m) => m.id === n.id)).toMatchObject({ x: n.x, y: n.y });
  const full = nodeGraph(data, index, data.nodes, route, 1000, 1000);
  expect(full.nodes).toHaveLength(NODE_LIMIT);
  expect(full.nodes[0].id).toBe('a');
  expect(new Set(full.nodes.map((n) => n.id)).size).toBe(NODE_LIMIT);
  const orphan = nodeGraph(data, index, data.nodes, {
    ...route,
    focus: 'orphan',
    gid: 'orphan',
    scope: 'hops2',
  });
  expect(orphan.nodes.map((n) => n.id)).toEqual(['orphan']);
  expect(orphan.edges).toHaveLength(0);
});

test('selection and expansion preserve anchor, zoom and dragged node positions', async ({
  page,
}) => {
  const gid = '100000003684369100';
  await page.goto(`/#graph?gid=${gid}&focus=${gid}&view=node&scope=hops1`);
  const graph = page.getByRole('img', { name: 'Интерактивный граф денежных переводов' });
  await expect(graph).toBeVisible();
  const getView = () =>
    graph.evaluate((el) => {
      const cy = (el as HTMLElement & { _cyreg: { cy: Core } })._cyreg.cy;
      return {
        zoom: cy.zoom(),
        positions: cy.nodes().map((n) => ({ id: n.id(), ...n.position() })),
      };
    });
  await page.getByRole('button', { name: 'Увеличить граф', exact: true }).click();
  await graph.evaluate((el) => {
    const cy = (el as HTMLElement & { _cyreg: { cy: Core } })._cyreg.cy;
    const n = cy.nodes()[1];
    n.position({ x: n.position('x') + 35, y: n.position('y') + 20 });
    n.emit('dragfree');
  });
  const before = await getView();
  await page.getByText('Участники на схеме', { exact: false }).click();
  const peer = before.positions.find((n) => n.id !== gid)!.id;
  await page.getByRole('button', { name: peer, exact: true }).first().click();
  await expect(page).toHaveURL(new RegExp(`focus=${gid}`));
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const after = await getView();
  expect(after.zoom).toBeCloseTo(before.zoom, 5);
  expect(after.positions).toEqual(before.positions);
  await page.getByRole('button', { name: 'Раскрыть связи', exact: true }).click();
  const expanded = await getView();
  expect(expanded.zoom).toBeCloseTo(before.zoom, 5);
  for (const n of before.positions)
    expect(expanded.positions.find((m) => m.id === n.id)).toEqual(n);
  await page.getByRole('button', { name: 'Сделать центром графа', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`focus=${peer}`));
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`focus=${gid}`));
});

test('cluster drilldown, edge details and direction filters are usable', async ({ page }) => {
  await page.goto('/#graph');
  await expect(page.getByRole('button', { name: 'Обзор кластеров', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page.getByRole('button', { name: 'Кластер 0', exact: true }).first().click();
  const panel = page.getByRole('complementary', { name: 'Сведения о выборе' });
  await expect(panel.getByText('Начать исследование с узла')).toBeVisible();
  await panel.getByRole('button', { name: /^100/ }).first().click();
  await expect(
    page.getByRole('button', { name: 'Исследование узла', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Входящие', exact: true }).click();
  await expect(page).toHaveURL(/direction=in/);
  await page
    .getByRole('button', { name: /^Поток / })
    .first()
    .click();
  await expect(page.getByText('Денежный поток', { exact: true })).toBeVisible();
  await expect(page.getByText(/Встречный поток отображается отдельной связью/)).toBeVisible();
  await page.getByRole('spinbutton', { name: 'Минимальная сумма перевода' }).fill('999999999999');
  await expect(
    page.getByText('В текущем окружении нет переводов, подходящих под условия.'),
  ).toBeVisible();
});

for (const width of [1440, 1024, 390])
  test(`node investigation remains usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/#graph?gid=100000003684369100&scope=hops2&card=open');
    await expect(
      page.getByRole('img', { name: 'Интерактивный граф денежных переводов' }),
    ).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Охват графа' })).toHaveValue('hops2');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await page.getByRole('combobox', { name: 'Охват графа' }).selectOption('hops1');
    const zoom = await page
      .getByRole('img', { name: 'Интерактивный граф денежных переводов' })
      .evaluate((el) => (el as HTMLElement & { _cyreg: { cy: Core } })._cyreg.cy.zoom());
    expect(zoom).toBeGreaterThan(width < 650 ? 0.2 : 0.4);
    await page.screenshot({ path: `test-results/investigation-${width}.png`, fullPage: true });
    await page.getByRole('button', { name: 'Закрыть карточку', exact: true }).click();
    await expect(page.getByRole('complementary', { name: 'Сведения о выборе' })).toHaveCount(0);
  });
