import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { indexGraph, nodeGraph, NODE_LIMIT } from '../src/graph';
import type { Dataset, Route } from '../src/types';

test('exact gid, graph, card, counterparty and deep link', async ({ page, request }) => {
  const data: Dataset = await (await request.get('/api/v1/dataset')).json();
  const gid = '100000003684369100';
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Обзор финансовой сети' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Глобальный поиск по gid' }).fill(gid);
  await page.getByRole('button', { name: 'Найти узел', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`gid=${gid}`));
  await expect(page.getByRole('img', { name: /Интерактивный граф/ })).toBeVisible();
  await expect(page.getByText('Строим связи…', { exact: true })).toBeHidden();
  await expect(page.locator('canvas').first()).toBeVisible();
  await page.reload();
  await expect(page.getByRole('combobox', { name: 'Охват графа' })).toHaveValue('hops1');
  await page.goto(`/#nodes?gid=${gid}&card=open`);
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: gid, exact: true })).toBeVisible();
  const edge = data.edges.filter((e) => e.dst === gid).sort((a, b) => b.sum_kzt - a.sum_kzt)[0];
  await dialog
    .getByRole('button', { name: new RegExp(edge.src) })
    .first()
    .click();
  await expect(
    page.getByRole('dialog').getByRole('heading', { name: edge.src, exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole('dialog').getByRole('heading', { name: gid, exact: true }),
  ).toBeVisible();
  await page.goForward();
  await page.getByRole('button', { name: /Показать окружение на графе/ }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`graph.*gid=${edge.src}`));
});

test('filters, pagination and CSV include all matching rows', async ({ page, request }) => {
  const data: Dataset = await (await request.get('/api/v1/dataset')).json();
  await page.goto('/#nodes');
  await page.getByRole('combobox', { name: 'Роль', exact: true }).selectOption('terminal');
  await page.getByRole('combobox', { name: 'Глубина' }).selectOption('2');
  const expected = data.nodes.filter((n) => n.role === 'terminal' && n.depth === 2);
  expect(expected.length).toBeGreaterThan(50);
  await expect(page.locator('tbody tr')).toHaveCount(50);
  await page.getByRole('button', { name: 'Следующая страница' }).click();
  await expect(page.getByRole('button', { name: 'Предыдущая страница' })).toBeEnabled();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Экспорт CSV' }).click();
  const download = await downloadPromise;
  const contents = await readFile((await download.path())!, 'utf8');
  expect(contents.split('\r\n')).toHaveLength(expected.length + 1);
  expect(contents).toContain(expected[0].gid);
  await page.getByRole('button', { name: 'Сбросить' }).click();
  await page.getByRole('textbox', { name: 'Фильтр по gid' }).fill('not-found');
  await expect(page.getByRole('heading', { name: 'Ничего не найдено' })).toBeVisible();
});

test('truncated node, cluster navigation and resilience', async ({ page, request }) => {
  const data: Dataset = await (await request.get('/api/v1/dataset')).json();
  const node = data.nodes.find((n) => n.depth === 4)!;
  await page.goto(`/#nodes?gid=${node.gid}&card=open`);
  await expect(page.getByText(/Обход остановлен на 4-м колене/)).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('link', { name: 'Кластеры', exact: true }).click();
  await page.getByRole('button', { name: 'Участники', exact: true }).first().click();
  await expect(page.getByRole('combobox', { name: 'Кластер', exact: true })).toHaveValue('0');
  await page.getByRole('link', { name: 'Устойчивость', exact: true }).click();
  await page.getByRole('button', { name: 'Топ-20', exact: true }).first().click();
  await expect(page.getByText('1 074', { exact: true }).first()).toBeVisible();
});

test('API failure can be retried; unknown gid is explained', async ({ page }) => {
  await page.route('**/api/v1/dataset', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Данные отсутствуют. Выполните ./run.sh' }),
    }),
  );
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Данные отсутствуют');
  await page.unroute('**/api/v1/dataset');
  await page.getByRole('button', { name: 'Повторить попытку' }).click();
  await expect(page.getByRole('heading', { name: 'Роли в сети' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Глобальный поиск по gid' }).fill('999999999999999999');
  await page.getByRole('button', { name: 'Найти узел', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Узел с таким gid не найден');
  await page.goto('/#graph?gid=999999999999999999');
  await expect(page.getByText('Узел 999999999999999999 не найден в этой выгрузке.')).toBeVisible();
});

for (const width of [1440, 1024, 390]) {
  test(`layout and navigation at ${width}px`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Роли в сети' })).toBeVisible();
    await page.screenshot({ path: `test-results/overview-${width}.png`, fullPage: true });
    const overflow = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      elements: [...document.querySelectorAll('body *')]
        .filter((el) => {
          const rect = el.getBoundingClientRect();
          return rect.right > window.innerWidth && getComputedStyle(el).position !== 'absolute';
        })
        .slice(0, 12)
        .map((el) => ({
          tag: el.tagName,
          className: el.className,
          right: el.getBoundingClientRect().right,
        })),
    }));
    expect(overflow.width, JSON.stringify(overflow)).toBeLessThanOrEqual(width);
    for (const section of ['nodes', 'clusters', 'resilience', 'graph']) {
      await page.goto(`/#${section}`);
      await expect(page.getByRole('main')).toBeVisible();
      if (section === 'graph') {
        await expect(page.getByRole('img', { name: /Интерактивный граф/ })).toBeVisible();
        await expect(page.getByText('Строим связи…', { exact: true })).toBeHidden();
      }
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBeTruthy();
    }
    await expect(page.getByText('Строим связи…', { exact: true })).toBeHidden();
    await page.screenshot({ path: `test-results/graph-${width}.png` });
    await page.getByRole('link', { name: 'Узлы', exact: true }).click();
    await page.getByRole('button', { name: '100000003684369100', exact: true }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.screenshot({ path: `test-results/card-${width}.png` });
    await page.keyboard.press('Escape');
    expect(errors).toEqual([]);
  });
}

test('graph caps displayed nodes and preserves selected orphan', async ({ request }) => {
  const data: Dataset = await (await request.get('/api/v1/dataset')).json();
  const orphan = data.nodes.find((n) => n.in_deg === 0 && n.out_deg === 0)!;
  const route: Route = {
    section: 'graph',
    gid: orphan.gid,
    card: '',
    q: '',
    role: '',
    cluster: '',
    depth: '',
    seed: '',
    scope: 'hops2',
    view: 'node',
    focus: orphan.gid,
    direction: 'all',
    minAmount: '',
  };
  expect(nodeGraph(data, indexGraph(data), data.nodes, route).nodes.map((n) => n.gid)).toEqual([
    orphan.gid,
  ]);
  const result = nodeGraph(data, indexGraph(data), data.nodes, {
    ...route,
    gid: data.top_nodes[0].gid,
    focus: data.top_nodes[0].gid,
    scope: 'hops2',
  });
  expect(result.nodes.length).toBeLessThanOrEqual(NODE_LIMIT);
  expect(result.nodes[0].gid).toBe(data.top_nodes[0].gid);
});
