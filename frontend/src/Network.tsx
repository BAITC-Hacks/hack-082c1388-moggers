import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  ChevronRight,
  Crosshair,
  Expand,
  Layers,
  Maximize,
  Minus,
  Network as NetworkIcon,
  Plus,
  RotateCcw,
  X,
} from 'lucide-react';
import type { Dataset, Edge, GraphNode, Route } from './types';
import { money, number } from './data';
import { clusterGraph, indexGraph, nodeGraph, NODE_LIMIT } from './graph';
import GraphCanvas, { type CanvasControls } from './GraphCanvas';
import s from './App.module.css';
import g from './Network.module.css';

interface Props {
  data: Dataset;
  filtered: GraphNode[];
  route: Route;
  go: (patch: Partial<Route>, replace?: boolean) => void;
  renderNode: (gid: string) => ReactNode;
}

export default function Network({ data, filtered, route, go, renderNode }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const canvas = useRef<CanvasControls>(null);
  const [clusterCount, setClusterCount] = useState(15);
  const [allClusterEdges, setAllClusterEdges] = useState(false);
  const [inLimit, setInLimit] = useState(10);
  const [outLimit, setOutLimit] = useState(10);
  const [expanded, setExpanded] = useState<string[]>([]);
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);
  const [fullScreenError, setFullScreenError] = useState('');
  const index = useMemo(() => indexGraph(data), [data]);
  const focus = route.focus || route.gid;
  const nodeMode = route.view === 'node';
  const anchor = index.nodes.get(focus);
  const chosenCluster = data.clusters.find((c) => String(c.cluster_id) === route.cluster);

  useEffect(() => {
    setInLimit(10);
    setOutLimit(10);
    setExpanded([]);
    setSelectedEdge(null);
  }, [focus, route.view]);
  useEffect(() => {
    if (route.scope !== 'hops2') setExpanded([]);
  }, [route.scope]);
  const fullModel = useMemo(
    () =>
      nodeMode
        ? nodeGraph(data, index, filtered, route, inLimit, outLimit, expanded)
        : clusterGraph(data, index, clusterCount, route.cluster),
    [data, index, filtered, route, nodeMode, inLimit, outLimit, expanded, clusterCount],
  );
  const model = useMemo(
    () =>
      !nodeMode && !allClusterEdges
        ? { ...fullModel, edges: fullModel.edges.slice(0, 30) }
        : fullModel,
    [fullModel, nodeMode, allClusterEdges],
  );
  const edge =
    selectedEdge &&
    model.edges.find((e) => e.src === selectedEdge.src && e.dst === selectedEdge.dst);
  const selected = nodeMode
    ? route.gid
    : chosenCluster
      ? `cluster:${chosenCluster.cluster_id}`
      : '';
  const hasPanel = Boolean(edge || (nodeMode ? route.gid && route.card === 'open' : chosenCluster));
  const displayed = new Set(model.nodes.map((n) => n.id));
  const canExpand =
    nodeMode && route.gid && displayed.has(route.gid) && !expanded.includes(route.gid);

  const selectNode = (id: string) => {
    setSelectedEdge(null);
    if (id.startsWith('cluster:')) go({ cluster: id.slice(8), gid: '', card: '' });
    else go({ gid: id, card: 'open' });
  };
  const investigate = (gid: string) => {
    setSelectedEdge(null);
    go({
      view: 'node',
      focus: gid,
      gid,
      card: 'open',
      scope: 'hops1',
      q: '',
      role: '',
      cluster: '',
      depth: '',
      seed: '',
      direction: 'all',
      minAmount: '',
    });
  };
  const closePanel = () => {
    setSelectedEdge(null);
    go(nodeMode ? { card: '' } : { cluster: '' });
  };
  const endpoint = (id: string) => (id.startsWith('cluster:') ? `Кластер ${id.slice(8)}` : id);
  const expandSelected = () => {
    if (canExpand && model.nodes.length < NODE_LIMIT) setExpanded((ids) => [...ids, route.gid]);
  };

  return (
    <section ref={root} className={g.workspace} aria-label="Исследование финансовой сети">
      <div className={g.modeBar}>
        <div className={g.modeTabs} role="group" aria-label="Режим графа">
          <button
            aria-pressed={!nodeMode}
            onClick={() => {
              setSelectedEdge(null);
              go({ view: 'clusters', card: '' });
            }}
          >
            <Layers size={16} />
            Обзор кластеров
          </button>
          <button
            aria-pressed={nodeMode}
            onClick={() => investigate(focus || data.top_nodes[0]?.gid || data.nodes[0]?.gid || '')}
          >
            <NetworkIcon size={16} />
            Исследование узла
          </button>
        </div>
        <button
          className={s.textButton}
          onClick={async () => {
            try {
              if (document.fullscreenElement) await document.exitFullscreen();
              else await root.current?.requestFullscreen();
              setFullScreenError('');
            } catch {
              setFullScreenError('Полноэкранный режим недоступен в этом браузере.');
            }
          }}
        >
          <Expand size={16} />
          На весь экран
        </button>
      </div>
      {fullScreenError && (
        <p className={g.notice} role="status">
          {fullScreenError}
        </p>
      )}
      <div className={g.toolbar}>
        {nodeMode ? (
          <>
            <div className={g.anchor}>
              <Crosshair size={17} />
              <div>
                <small>ЦЕНТР ИССЛЕДОВАНИЯ</small>
                <strong>{anchor?.gid || 'Выберите участника'}</strong>
              </div>
            </div>
            <div className={g.direction} role="group" aria-label="Направление переводов">
              {(
                [
                  ['all', 'Все'],
                  ['in', 'Входящие'],
                  ['out', 'Исходящие'],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  aria-pressed={route.direction === value}
                  onClick={() => go({ direction: value })}
                >
                  {label}
                </button>
              ))}
            </div>
            <label className={g.amountLabel}>
              От, ₸
              <input
                aria-label="Минимальная сумма перевода"
                type="number"
                min="0"
                step="5000"
                placeholder="0"
                value={route.minAmount}
                onChange={(e) => go({ minAmount: e.target.value }, true)}
              />
            </label>
            <select
              aria-label="Охват графа"
              value={route.scope === 'hops2' ? 'hops2' : 'hops1'}
              onChange={(e) => go({ scope: e.target.value })}
            >
              <option value="hops1">Прямые связи</option>
              <option value="hops2">Два колена</option>
            </select>
          </>
        ) : (
          <>
            <div className={g.overviewTitle}>
              <strong>Крупные сообщества и потоки между ними</strong>
              <span>Размер — число участников. Синие кластеры объединяют несколько seed.</span>
            </div>
            <label className={g.edgeLimit}>
              Связи
              <select
                aria-label="Связи между кластерами"
                value={allClusterEdges ? 'all' : 'top'}
                onChange={(e) => setAllClusterEdges(e.target.value === 'all')}
              >
                <option value="top">Крупнейшие 30</option>
                <option value="all">Все {fullModel.edges.length}</option>
              </select>
            </label>
          </>
        )}
      </div>

      <div className={`${g.graphGrid} ${hasPanel ? g.withPanel : ''}`}>
        <div className={g.plot}>
          {nodeMode && (
            <div className={g.lanes} aria-hidden="true">
              <span>
                Плательщики <ArrowRight size={12} />
              </span>
              <span>Узел / встречные связи</span>
              <span>
                <ArrowRight size={12} /> Получатели
              </span>
            </div>
          )}
          <GraphCanvas
            ref={canvas}
            model={model}
            viewKey={nodeMode ? `node:${focus}:${route.scope}` : 'clusters'}
            focus={nodeMode ? focus : selected}
            selected={selected}
            selectedEdge={edge ? `${edge.src}>${edge.dst}` : ''}
            onNode={selectNode}
            onEdge={setSelectedEdge}
          />
          <div className={g.plotControls}>
            <button aria-label="Увеличить граф" onClick={() => canvas.current?.zoom(1.25)}>
              <Plus size={18} />
            </button>
            <button aria-label="Уменьшить граф" onClick={() => canvas.current?.zoom(0.8)}>
              <Minus size={18} />
            </button>
            <button aria-label="Вписать граф в экран" onClick={() => canvas.current?.fit()}>
              <Maximize size={17} />
            </button>
            <button
              aria-label="Центрировать выбранный узел"
              disabled={!selected && !focus}
              onClick={() => canvas.current?.center()}
            >
              <Crosshair size={17} />
            </button>
            <button aria-label="Перестроить схему" onClick={() => canvas.current?.reset()}>
              <RotateCcw size={17} />
            </button>
          </div>
          <div className={g.plotHelp}>
            Перетаскивайте узлы · Нажмите на связь, чтобы увидеть сумму
          </div>
        </div>
        {hasPanel && (
          <aside className={g.inspector} aria-label="Сведения о выборе">
            {edge ? (
              <div className={g.edgeCard}>
                <div className={g.inspectorHeading}>
                  <span>Денежный поток</span>
                  <button aria-label="Закрыть сведения о потоке" onClick={closePanel}>
                    <X size={19} />
                  </button>
                </div>
                <div className={g.transferPath}>
                  <button onClick={() => selectNode(edge.src)}>{endpoint(edge.src)}</button>
                  <ArrowRight size={18} />
                  <button onClick={() => selectNode(edge.dst)}>{endpoint(edge.dst)}</button>
                </div>
                <strong className={g.transferAmount}>{money(edge.sum_kzt)}</strong>
                <p>{number(edge.n_tx)} переводов за период</p>
                <div className={g.notice}>
                  Это сумма переводов в указанном направлении. Встречный поток отображается
                  отдельной связью.
                </div>
              </div>
            ) : nodeMode ? (
              <>
                <div className={g.nodeActions}>
                  <button
                    className={s.secondaryButton}
                    disabled={!canExpand || model.nodes.length >= NODE_LIMIT}
                    onClick={expandSelected}
                  >
                    <Plus size={15} />
                    Раскрыть связи
                  </button>
                  <span>
                    {expanded.includes(route.gid) ? 'Связи раскрыты' : 'До 10 в каждом направлении'}
                  </span>
                </div>
                {renderNode(route.gid)}
              </>
            ) : (
              chosenCluster && (
                <div className={g.clusterCard}>
                  <div className={g.inspectorHeading}>
                    <span>Кластер {chosenCluster.cluster_id}</span>
                    <button aria-label="Закрыть сведения о кластере" onClick={closePanel}>
                      <X size={19} />
                    </button>
                  </div>
                  <div className={g.clusterMetrics}>
                    <div>
                      <strong>{number(chosenCluster.n_nodes)}</strong>
                      <span>участников</span>
                    </div>
                    <div>
                      <strong>{chosenCluster.n_seed}</strong>
                      <span>seed</span>
                    </div>
                  </div>
                  <p className={g.internalFlow}>
                    Внутренний оборот <strong>{money(chosenCluster.sum_kzt_internal)}</strong>
                  </p>
                  <p className={g.hypothesis}>{chosenCluster.hypothesis}</p>
                  <h3>Начать исследование с узла</h3>
                  {chosenCluster.top_gids.map((gid) => (
                    <button key={gid} className={g.clusterNode} onClick={() => investigate(gid)}>
                      <span>{gid}</span>
                      <ChevronRight size={15} />
                    </button>
                  ))}
                  <button
                    className={s.secondaryButton}
                    onClick={() =>
                      go({
                        section: 'nodes',
                        gid: '',
                        card: '',
                        q: '',
                        role: '',
                        depth: '',
                        seed: '',
                      })
                    }
                  >
                    Все участники кластера
                    <ArrowRight size={15} />
                  </button>
                </div>
              )
            )}
          </aside>
        )}
      </div>

      <div className={g.statusBar}>
        <span>
          <b>{model.nodes.length}</b> из {number(model.total)}{' '}
          {nodeMode ? 'узлов окружения' : 'кластеров'} · <b>{model.edges.length}</b>
          {!nodeMode && model.edges.length < fullModel.edges.length
            ? ` из ${fullModel.edges.length}`
            : ''}{' '}
          связей
        </span>
        {nodeMode ? (
          <div className={g.moreButtons}>
            <button
              disabled={inLimit >= fullModel.incomingTotal || model.nodes.length >= NODE_LIMIT}
              onClick={() => setInLimit((x) => x + 10)}
            >
              <ArrowLeft size={13} />
              Ещё 10 входящих
            </button>
            <button
              disabled={outLimit >= fullModel.outgoingTotal || model.nodes.length >= NODE_LIMIT}
              onClick={() => setOutLimit((x) => x + 10)}
            >
              Ещё 10 исходящих
              <ArrowRight size={13} />
            </button>
          </div>
        ) : (
          <button
            className={s.textButton}
            disabled={clusterCount >= fullModel.total}
            onClick={() => setClusterCount((n) => n + 15)}
          >
            Ещё 15 кластеров
            <Plus size={14} />
          </button>
        )}
      </div>
      {nodeMode && model.nodes.length >= NODE_LIMIT && (
        <div className={g.notice} role="status">
          Достигнут предел {NODE_LIMIT} узлов. Выберите новый центр или уточните фильтры, чтобы
          продолжить исследование.
        </div>
      )}
      {nodeMode && focus && !anchor && (
        <div className={g.notice} role="status">
          Узел {focus} не найден в этой выгрузке.
        </div>
      )}

      <details className={g.participants} open={!nodeMode}>
        <summary>
          {nodeMode ? 'Участники на схеме' : 'Кластеры на схеме'} <span>{model.nodes.length}</span>
        </summary>
        <div className={g.nodeChips}>
          {model.nodes.map((n) => (
            <button key={n.id} onClick={() => selectNode(n.id)} aria-pressed={selected === n.id}>
              <i style={{ background: n.color }} />
              {nodeMode ? n.gid : `Кластер ${n.clusterId}`}
            </button>
          ))}
        </div>
      </details>
      <details className={g.transfers} open>
        <summary>
          Переводы на схеме <span>{model.edges.length}</span>
        </summary>
        {model.edges.length ? (
          <div className={g.transferTable}>
            <table>
              <thead>
                <tr>
                  <th>Отправитель</th>
                  <th>Получатель</th>
                  <th>Сумма</th>
                  <th>Переводов</th>
                  <th>Сведения</th>
                </tr>
              </thead>
              <tbody>
                {model.edges.map((e) => (
                  <tr
                    key={`${e.src}>${e.dst}`}
                    className={edge?.src === e.src && edge?.dst === e.dst ? g.activeRow : ''}
                  >
                    <td>
                      <button onClick={() => selectNode(e.src)}>{endpoint(e.src)}</button>
                    </td>
                    <td>
                      <button onClick={() => selectNode(e.dst)}>{endpoint(e.dst)}</button>
                    </td>
                    <td>{money(e.sum_kzt)}</td>
                    <td>{number(e.n_tx)}</td>
                    <td>
                      <button
                        aria-label={`Поток ${endpoint(e.src)} → ${endpoint(e.dst)}`}
                        onClick={() => setSelectedEdge(e)}
                      >
                        Открыть
                        <ChevronRight size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className={g.noTransfers}>
            В текущем окружении нет переводов, подходящих под условия.
          </p>
        )}
      </details>
    </section>
  );
}
