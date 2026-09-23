import {
  lazy,
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react';
import {
  Activity,
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Copy,
  Download,
  GitBranch,
  Layers,
  LayoutDashboard,
  ListFilter,
  Network as NetworkIcon,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Users,
  Wallet,
  X,
  AlertTriangle,
  RefreshCw,
  CalendarDays,
} from 'lucide-react';
import type { Dataset, GraphNode, Route, Section } from './types';
import {
  exportCsv,
  filterNodes,
  money,
  number,
  percent,
  readRoute,
  roleOrder,
  score,
  validateDataset,
  writeRoute,
} from './data';
import s from './App.module.css';

const Network = lazy(() => import('./Network'));

const nav = [
  {
    id: 'overview',
    title: 'Обзор',
    icon: LayoutDashboard,
    description: 'От переводов — к структуре сети',
  },
  {
    id: 'graph',
    title: 'Граф связей',
    icon: NetworkIcon,
    description: 'Исследуйте маршруты денег и связи между участниками',
  },
  {
    id: 'nodes',
    title: 'Узлы',
    icon: Users,
    description: 'Каждый участник сети и основания для его проверки',
  },
  {
    id: 'clusters',
    title: 'Кластеры',
    icon: Layers,
    description: 'Сообщества, объединённые денежными переводами',
  },
  {
    id: 'resilience',
    title: 'Устойчивость',
    icon: ShieldCheck,
    description: 'Как меняется сеть при изъятии ключевых узлов',
  },
] as const;
const cleanFilters = { q: '', role: '', cluster: '', depth: '', seed: '' };

function RoleBadge({ role, data }: { role: string; data: Dataset }) {
  const color = data.role_styles[role]?.color || '#64748b';
  const shape = data.role_styles[role]?.shape;
  return (
    <span className={s.roleBadge} style={{ '--role-color': color } as CSSProperties}>
      <i
        style={{
          borderRadius: shape === 'ellipse' ? '50%' : 1,
          transform: shape === 'diamond' ? 'rotate(45deg)' : undefined,
          clipPath:
            shape === 'triangle'
              ? 'polygon(50% 0, 100% 100%, 0 100%)'
              : shape === 'hexagon'
                ? 'polygon(25% 0, 75% 0, 100% 50%, 75% 100%, 25% 100%, 0 50%)'
                : undefined,
        }}
      />
      {data.role_labels[role] || role}
    </span>
  );
}
function Metric({
  icon,
  label,
  value,
  note,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className={s.metric}>
      <div className={s.metricLabel}>
        {label}
        <span>{icon}</span>
      </div>
      <div className={s.metricValue}>{value}</div>
      <div className={s.metricNote}>{note}</div>
    </div>
  );
}
function Empty({ children }: { children: ReactNode }) {
  return (
    <div className={s.empty}>
      <Search size={28} />
      <h3>Ничего не найдено</h3>
      <p>{children}</p>
    </div>
  );
}

export default function App() {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [route, setRoute] = useState(readRoute);
  const [search, setSearch] = useState('');
  const [searchMessage, setSearchMessage] = useState('');
  useEffect(() => {
    const listener = () => setRoute(readRoute());
    window.addEventListener('hashchange', listener);
    return () => window.removeEventListener('hashchange', listener);
  }, []);
  useEffect(() => {
    const abort = new AbortController();
    setError('');
    fetch('/api/v1/dataset', { signal: abort.signal })
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(
            typeof body.detail === 'string' ? body.detail : 'Не удалось загрузить данные анализа.',
          );
        }
        return response.json();
      })
      .then(validateDataset)
      .then(setData)
      .catch((e) => {
        if (e.name !== 'AbortError')
          setError(
            e.message === 'Failed to fetch'
              ? 'Сервер недоступен. Проверьте соединение и повторите попытку.'
              : e.message,
          );
      });
    return () => abort.abort();
  }, [attempt]);
  const go = (patch: Partial<Route>, replace = false) =>
    writeRoute({ ...route, ...patch }, replace);
  const selected = data?.nodes.find((n) => n.gid === route.gid);
  const filtered = useMemo(() => (data ? filterNodes(data.nodes, route) : []), [data, route]);
  const active = nav.find((item) => item.id === route.section)!;
  const select = (gid: string) => go({ gid, card: 'open' });
  const showGraph = (gid: string) =>
    go({
      section: 'graph',
      view: 'node',
      focus: gid,
      gid,
      card: 'open',
      scope: 'hops1',
      direction: 'all',
      minAmount: '',
      ...cleanFilters,
    });

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    const q = search.trim();
    if (!q || !data) return;
    setSearchMessage('');
    if (data.nodes.some((n) => n.gid === q)) {
      showGraph(q);
      setSearch('');
    } else if (data.nodes.some((n) => n.gid.includes(q))) {
      go({ section: 'nodes', gid: '', ...cleanFilters, q });
      setSearch('');
    } else setSearchMessage('Узел с таким gid не найден');
  }

  return (
    <div className={s.app}>
      <aside className={s.sidebar}>
        <a className={s.brand} href="#overview" aria-label="MoneyGraph — обзор">
          <span className={s.brandMark}>
            <GitBranch size={25} />
          </span>
          <span>
            moneygraph<span className={s.brandSub}>FINANCIAL INTELLIGENCE</span>
          </span>
        </a>
        <div className={s.workspace}>
          <span className={s.workspaceIcon}>F</span>
          <div>
            <strong>Граф денег</strong>
            <small>Рабочее пространство</small>
          </div>
          <span className={s.liveDot} />
        </div>
        <div className={s.navLabel}>АНАЛИЗ СЕТИ</div>
        <nav aria-label="Основная навигация">
          {nav.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              aria-label={item.title}
              title={item.title}
              className={`${s.navItem} ${route.section === item.id ? s.navActive : ''}`}
              aria-current={route.section === item.id ? 'page' : undefined}
            >
              <item.icon size={19} />
              <span>{item.title}</span>
              {item.id === 'nodes' && data && <small>{number(data.nodes.length)}</small>}
            </a>
          ))}
          <a className={s.navItem} href="/assistant#tab=chat" aria-label="ИИ-ассистент">
            <CircleHelp size={20} />
            <span>ИИ-ассистент</span>
          </a>
        </nav>
        <div className={s.sidebarBottom}>
          <div className={s.localNote}>
            <ShieldCheck size={20} />
            <strong>Данные под контролем</strong>
            <p>Анализ внутрибанковских переводов. Обезличенные идентификаторы.</p>
          </div>
          <div className={s.analyst}>
            <span>А</span>
            <div>
              <strong>Рабочее место аналитика</strong>
              <small>Финансовый мониторинг</small>
            </div>
          </div>
        </div>
      </aside>

      <div className={s.main}>
        <header className={s.topbar}>
          <div className={s.breadcrumb}>
            Рабочее пространство <ChevronRight size={14} /> <strong>{active.title}</strong>
          </div>
          <form className={s.globalSearch} onSubmit={submitSearch}>
            <Search size={17} />
            <input
              aria-label="Глобальный поиск по gid"
              placeholder="Найти узел по gid…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setSearchMessage('');
              }}
            />
            <button aria-label="Найти узел" type="submit" disabled={!data}>
              <ArrowRight size={16} />
            </button>
            {searchMessage && (
              <span role="status" className={s.searchMessage}>
                {searchMessage}
              </span>
            )}
          </form>
          <div className={s.avatar} aria-hidden="true">
            А
          </div>
        </header>

        <main className={s.content}>
          <div className={s.pageHeading}>
            <div>
              <div className={s.eyebrow}>MONEYGRAPH / АНАЛИТИКА</div>
              <h1>{active.title === 'Обзор' ? 'Обзор финансовой сети' : active.title}</h1>
              <p>{active.description}</p>
            </div>
            {data && (
              <div className={s.period}>
                <CalendarDays size={17} />
                <span>
                  {data.summary.period
                    .map((day) => new Date(`${day}T00:00:00`).toLocaleDateString('ru-RU'))
                    .join(' — ')}
                </span>
              </div>
            )}
          </div>
          {error ? (
            <div className={s.error} role="alert">
              <AlertTriangle size={30} />
              <h2>Не удалось открыть анализ</h2>
              <p>{error}</p>
              <button className={s.primaryButton} onClick={() => setAttempt((x) => x + 1)}>
                <RefreshCw size={16} />
                Повторить попытку
              </button>
            </div>
          ) : !data ? (
            <div className={s.loading} role="status">
              <div className={s.spinner} />
              <h2>Загружаем финансовую сеть</h2>
              <p>Узлы, связи и результаты анализа</p>
            </div>
          ) : (
            <>
              {route.section === 'overview' && (
                <Overview
                  data={data}
                  onSelect={select}
                  onNavigate={(section) => go({ section, gid: '', ...cleanFilters })}
                  onRole={(role) => go({ section: 'nodes', ...cleanFilters, role })}
                />
              )}
              {(route.section === 'nodes' || route.section === 'graph') && (
                <>
                  {(route.section === 'nodes' || route.view === 'node') && (
                    <Filters data={data} route={route} go={go} />
                  )}
                  {route.section === 'nodes' ? (
                    <NodeTable data={data} nodes={filtered} onSelect={select} />
                  ) : (
                    <>
                      <Suspense
                        fallback={
                          <div className={s.loading} role="status">
                            Загружаем граф…
                          </div>
                        }
                      >
                        <Network
                          data={data}
                          filtered={filtered}
                          route={route}
                          go={go}
                          renderNode={(gid) => (
                            <NodeCard
                              key={gid}
                              inline
                              data={data}
                              node={data.nodes.find((n) => n.gid === gid)}
                              gid={gid}
                              onClose={() => go({ card: '' })}
                              onSelect={select}
                              onGraph={showGraph}
                              onCluster={(cluster) =>
                                go({
                                  section: 'nodes',
                                  gid: '',
                                  card: '',
                                  ...cleanFilters,
                                  cluster: String(cluster),
                                })
                              }
                            />
                          )}
                        />
                      </Suspense>
                      <div className={s.legend}>
                        {roleOrder.map((role) => (
                          <RoleBadge key={role} data={data} role={role} />
                        ))}
                      </div>
                      <p className={s.footnote}>
                        Для выбора узла с клавиатуры воспользуйтесь поиском или таблицей узлов.
                      </p>
                    </>
                  )}
                </>
              )}
              {route.section === 'clusters' && (
                <Clusters
                  data={data}
                  onSelect={select}
                  onOpen={(cluster, section) =>
                    go({
                      section,
                      gid: '',
                      view: 'clusters',
                      focus: '',
                      ...cleanFilters,
                      cluster: String(cluster),
                      scope: 'top',
                    })
                  }
                />
              )}
              {route.section === 'resilience' && <ResilienceView data={data} />}
              <footer className={s.footer}>
                <span>
                  <CircleHelp size={14} /> Роли и связи — гипотезы для проверки, а не выводы о
                  виновности.
                </span>
                <span>
                  <span className={s.statusDot} /> Локальный анализ
                </span>
              </footer>
            </>
          )}
        </main>
      </div>
      {data && route.section !== 'graph' && route.gid && (route.card === 'open' || !selected) && (
        <NodeCard
          key={route.gid}
          data={data}
          node={selected}
          gid={route.gid}
          onClose={() => go(selected ? { card: '' } : { gid: '', card: '' })}
          onSelect={select}
          onGraph={showGraph}
          onCluster={(cluster) =>
            go({ section: 'nodes', gid: '', card: '', ...cleanFilters, cluster: String(cluster) })
          }
        />
      )}
    </div>
  );
}

function Overview({
  data,
  onSelect,
  onNavigate,
  onRole,
}: {
  data: Dataset;
  onSelect: (gid: string) => void;
  onNavigate: (section: Section) => void;
  onRole: (role: string) => void;
}) {
  const impact = data.resilience.find((r) => r.removed_top_n === 10);
  const counts = roleOrder.map((role) => ({
    role,
    count: data.nodes.filter((n) => n.role === role).length,
  }));
  const maxCount = Math.max(...counts.map((r) => r.count), 1);
  const nodes = new Map(data.nodes.map((n) => [n.gid, n]));
  return (
    <>
      <div className={s.metrics}>
        <Metric
          icon={<Users size={19} />}
          label="Участники сети"
          value={number(data.summary.n_nodes)}
          note={`${number(data.summary.n_seed)} исходный seed-клиент`}
        />
        <Metric
          icon={<ArrowUpRight size={20} />}
          label="Денежные переводы"
          value={number(data.summary.n_tx)}
          note={`${number(data.summary.n_edges)} направленных связей`}
        />
        <Metric
          icon={<Wallet size={19} />}
          label="Оборот сети"
          value={money(data.summary.turnover_kzt)}
          note="Внутрибанковские переводы за период"
        />
        <Metric
          icon={<Layers size={19} />}
          label="Выявленные кластеры"
          value={number(data.clusters.length)}
          note={`${data.clusters.filter((c) => c.n_seed > 1).length} объединяют несколько seed`}
        />
      </div>
      <div className={s.overviewGrid}>
        <section className={s.insight}>
          <div className={s.insightTop}>
            <span className={s.insightLabel}>
              <Activity size={14} /> СТРУКТУРА СЕТИ
            </span>
            <span className={s.insightTag}>4 колена переводов</span>
          </div>
          <h2>
            Увидеть связи.
            <br />
            Определить приоритет.
          </h2>
          <p>
            От отдельных переводов к целостной картине: найдите узлы, которые связывают участников и
            распределяют потоки.
          </p>
          <button className={s.whiteButton} onClick={() => onNavigate('graph')}>
            Исследовать граф <ArrowRight size={17} />
          </button>
          <svg className={s.insightNetwork} viewBox="0 0 320 240" aria-hidden="true">
            <g stroke="#91b9ff" strokeOpacity=".3">
              {[
                [70, 80, 165, 100],
                [165, 100, 230, 40],
                [165, 100, 255, 150],
                [70, 80, 50, 175],
                [50, 175, 165, 100],
                [165, 100, 170, 205],
                [170, 205, 255, 150],
                [70, 80, 135, 25],
                [135, 25, 230, 40],
                [255, 150, 295, 85],
                [230, 40, 295, 85],
              ].map((p, i) => (
                <line key={i} x1={p[0]} y1={p[1]} x2={p[2]} y2={p[3]} />
              ))}
            </g>
            {[
              [70, 80, 9],
              [165, 100, 19],
              [230, 40, 11],
              [255, 150, 13],
              [50, 175, 7],
              [170, 205, 8],
              [135, 25, 6],
              [295, 85, 5],
            ].map((p, i) => (
              <g key={i}>
                <circle cx={p[0]} cy={p[1]} r={p[2] + 7} fill="#8eb6ff" opacity=".07" />
                <circle
                  cx={p[0]}
                  cy={p[1]}
                  r={p[2]}
                  fill={i === 1 ? '#fff' : '#8eb6ff'}
                  opacity={i === 1 ? '.95' : '.65'}
                />
              </g>
            ))}
          </svg>
          {impact && (
            <div className={s.insightBottom}>
              <strong>{percent(1 - impact.reachable_share)}</strong>
              <span>
                узлов теряют достижимость от seed
                <br />
                при изъятии топ-10
              </span>
              <button
                aria-label="Подробнее об устойчивости"
                onClick={() => onNavigate('resilience')}
              >
                <ArrowUpRight size={21} />
              </button>
            </div>
          )}
        </section>
        <section className={s.card}>
          <div className={s.cardHeading}>
            <div>
              <h2>Роли в сети</h2>
              <p>Распределение участников</p>
            </div>
            <span className={s.smallTag}>7 ролей</span>
          </div>
          <div className={s.roleDistribution}>
            {counts.map(({ role, count }) => (
              <button key={role} className={s.roleRow} onClick={() => onRole(role)}>
                <span>
                  <RoleBadge role={role} data={data} />
                  <strong>{number(count)}</strong>
                </span>
                <div className={s.roleTrack}>
                  <i
                    style={{
                      width: `${(count / maxCount) * 100}%`,
                      background: data.role_styles[role].color,
                    }}
                  />
                </div>
              </button>
            ))}
          </div>
        </section>
      </div>
      <section className={s.card}>
        <div className={s.cardHeading}>
          <div>
            <h2>
              Кого проверить первым <span className={s.smallTag}>ТОП {data.top_nodes.length}</span>
            </h2>
            <p>Узлы с наибольшим приоритетом и объяснением позиции</p>
          </div>
          <button className={s.textButton} onClick={() => onNavigate('nodes')}>
            Все узлы <ArrowRight size={16} />
          </button>
        </div>
        <div className={s.tableScroll}>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Идентификатор узла</th>
                <th>Роль</th>
                <th>Приоритет</th>
                <th>Основание для проверки</th>
                <th>
                  <span className={s.srOnly}>Открыть</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.top_nodes.map((top) => (
                <tr key={top.gid}>
                  <td className={s.rank}>{String(top.rank).padStart(2, '0')}</td>
                  <td>
                    <button className={s.gidButton} onClick={() => onSelect(top.gid)}>
                      {top.gid}
                    </button>
                    {nodes.get(top.gid)?.is_seed && <span className={s.seedLabel}>SEED</span>}
                  </td>
                  <td>
                    <RoleBadge role={top.role} data={data} />
                  </td>
                  <td>
                    <Priority value={top.priority_score} />
                  </td>
                  <td className={s.why}>{top.why}</td>
                  <td>
                    <button
                      className={s.iconButton}
                      aria-label={`Открыть узел ${top.gid}`}
                      onClick={() => onSelect(top.gid)}
                    >
                      <ArrowUpRight size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function Priority({ value }: { value: number }) {
  return (
    <span className={s.priority}>
      <strong>{score(value)}</strong>
      <i>
        <b style={{ width: `${value * 100}%` }} />
      </i>
    </span>
  );
}

function Filters({
  data,
  route,
  go,
}: {
  data: Dataset;
  route: Route;
  go: (patch: Partial<Route>, replace?: boolean) => void;
}) {
  const active = Object.keys(cleanFilters).some((key) => route[key as keyof Route]);
  return (
    <div className={s.filters}>
      <div className={s.filterSearch}>
        <Search size={17} />
        <input
          aria-label="Фильтр по gid"
          placeholder="Поиск по gid"
          value={route.q}
          onChange={(e) => go({ q: e.target.value }, true)}
        />
      </div>
      <select aria-label="Роль" value={route.role} onChange={(e) => go({ role: e.target.value })}>
        <option value="">Все роли</option>
        {roleOrder.map((role) => (
          <option key={role} value={role}>
            {data.role_labels[role]}
          </option>
        ))}
      </select>
      <select
        aria-label="Кластер"
        value={route.cluster}
        onChange={(e) => go({ cluster: e.target.value })}
      >
        <option value="">Все кластеры</option>
        {data.clusters.map((c) => (
          <option key={c.cluster_id} value={c.cluster_id}>
            Кластер {c.cluster_id} · {c.n_nodes}
          </option>
        ))}
      </select>
      <select
        aria-label="Глубина"
        value={route.depth}
        onChange={(e) => go({ depth: e.target.value })}
      >
        <option value="">Все колена</option>
        {[0, 1, 2, 3, 4].map((n) => (
          <option key={n} value={n}>
            {n === 0 ? 'Seed · 0' : `Колено ${n}`}
          </option>
        ))}
      </select>
      <select aria-label="Seed" value={route.seed} onChange={(e) => go({ seed: e.target.value })}>
        <option value="">Все участники</option>
        <option value="yes">Только seed</option>
        <option value="no">Без seed</option>
      </select>
      {active ? (
        <button className={s.textButton} onClick={() => go(cleanFilters)}>
          <X size={15} />
          Сбросить
        </button>
      ) : (
        <SlidersHorizontal className={s.filterIcon} size={18} />
      )}
    </div>
  );
}

function NodeTable({
  data,
  nodes,
  onSelect,
}: {
  data: Dataset;
  nodes: GraphNode[];
  onSelect: (gid: string) => void;
}) {
  const [sort, setSort] = useState<keyof GraphNode>('priority_score');
  const [asc, setAsc] = useState(false);
  const [page, setPage] = useState(0);
  const sorted = useMemo(
    () =>
      [...nodes].sort((a, b) => {
        const left = a[sort],
          right = b[sort];
        const result =
          typeof left === 'number' && typeof right === 'number'
            ? left - right
            : String(left).localeCompare(String(right));
        return (asc ? result : -result) || a.gid.localeCompare(b.gid);
      }),
    [nodes, sort, asc],
  );
  useEffect(() => setPage(0), [nodes, sort, asc]);
  const last = Math.max(0, Math.ceil(sorted.length / 50) - 1);
  const current = Math.min(page, last);
  function sortBy(field: keyof GraphNode) {
    if (sort === field) setAsc(!asc);
    else {
      setSort(field);
      setAsc(field === 'gid');
    }
  }
  const columns: [keyof GraphNode, string][] = [
    ['gid', 'Идентификатор'],
    ['role', 'Роль'],
    ['priority_score', 'Приоритет'],
    ['cluster_id', 'Кластер'],
    ['in_kzt', 'Входящие'],
    ['out_kzt', 'Исходящие'],
    ['depth', 'Колено'],
  ];
  return (
    <section className={s.card}>
      <div className={s.cardHeading}>
        <div>
          <h2>
            Участники сети <span className={s.smallTag}>{number(nodes.length)}</span>
          </h2>
          <p>Сортируйте и выбирайте узлы для изучения</p>
        </div>
        <button
          className={s.secondaryButton}
          disabled={!nodes.length}
          onClick={() => exportCsv(sorted)}
        >
          <Download size={16} />
          Экспорт CSV
        </button>
      </div>
      {!nodes.length ? (
        <Empty>Измените поисковый запрос или сбросьте фильтры.</Empty>
      ) : (
        <>
          <div className={s.tableScroll}>
            <table>
              <thead>
                <tr>
                  {columns.map(([field, label]) => (
                    <th
                      key={field}
                      aria-sort={sort === field ? (asc ? 'ascending' : 'descending') : 'none'}
                    >
                      <button onClick={() => sortBy(field)}>
                        {label}
                        <span>{sort === field ? (asc ? ' ↑' : ' ↓') : ' ↕'}</span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.slice(current * 50, current * 50 + 50).map((n) => (
                  <tr key={n.gid}>
                    <td>
                      <button className={s.gidButton} onClick={() => onSelect(n.gid)}>
                        {n.gid}
                      </button>
                      {n.is_seed && <span className={s.seedLabel}>SEED</span>}
                    </td>
                    <td>
                      <RoleBadge role={n.role} data={data} />
                    </td>
                    <td>
                      <Priority value={n.priority_score} />
                    </td>
                    <td>
                      <span className={s.clusterLabel}>#{n.cluster_id}</span>
                    </td>
                    <td className={s.numeric}>{money(n.in_kzt)}</td>
                    <td className={s.numeric}>{money(n.out_kzt)}</td>
                    <td>
                      {n.depth}
                      {n.depth_truncated && (
                        <span title="Обход остановлен" className={s.truncated}>
                          *
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className={s.pagination}>
            <span>
              {current * 50 + 1}–{Math.min(current * 50 + 50, sorted.length)} из{' '}
              {number(sorted.length)} узлов
            </span>
            <div>
              <button
                aria-label="Предыдущая страница"
                disabled={current === 0}
                onClick={() => setPage(current - 1)}
              >
                <ChevronLeft size={17} />
              </button>
              <span>
                {current + 1} / {last + 1}
              </span>
              <button
                aria-label="Следующая страница"
                disabled={current === last}
                onClick={() => setPage(current + 1)}
              >
                <ChevronRight size={17} />
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function Clusters({
  data,
  onSelect,
  onOpen,
}: {
  data: Dataset;
  onSelect: (gid: string) => void;
  onOpen: (id: number, section: Section) => void;
}) {
  const [q, setQ] = useState('');
  const [multiSeed, setMultiSeed] = useState(false);
  const list = data.clusters.filter(
    (c) => String(c.cluster_id).includes(q.trim()) && (!multiSeed || c.n_seed > 1),
  );
  return (
    <>
      <div className={s.filters}>
        <div className={s.filterSearch}>
          <Search size={17} />
          <input
            aria-label="Поиск кластера"
            placeholder="Номер кластера"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <label className={s.checkbox}>
          <input
            type="checkbox"
            checked={multiSeed}
            onChange={(e) => setMultiSeed(e.target.checked)}
          />
          Несколько seed
        </label>
        <span className={s.muted}>
          {list.length} из {data.clusters.length} кластеров
        </span>
      </div>
      <div className={s.infoBanner}>
        <Layers size={19} />
        <span>
          Кластеры показывают связанность участников. Направление переводов учитывается в ролях и на
          графе.
        </span>
      </div>
      {!list.length ? (
        <Empty>Кластер с такими параметрами не найден.</Empty>
      ) : (
        <div className={s.clusterGrid}>
          {list.map((c) => (
            <section className={s.clusterCard} key={c.cluster_id}>
              <div className={s.clusterHeader}>
                <span className={s.clusterIcon}>
                  <Layers size={20} />
                </span>
                <h2>Кластер {String(c.cluster_id).padStart(2, '0')}</h2>
                <span className={s.smallTag}>{c.n_seed} seed</span>
              </div>
              <div className={s.clusterStats}>
                <div>
                  <strong>{number(c.n_nodes)}</strong>
                  <span>участников</span>
                </div>
                <div>
                  <strong>{money(c.sum_kzt_internal)}</strong>
                  <span>внутренний оборот</span>
                </div>
              </div>
              <p className={s.hypothesis}>{c.hypothesis}</p>
              <div className={s.miniLabel}>КЛЮЧЕВЫЕ УЗЛЫ</div>
              <div className={s.clusterNodes}>
                {c.top_gids.map((gid) => (
                  <button key={gid} className={s.gidButton} onClick={() => onSelect(gid)}>
                    {gid}
                    <ArrowUpRight size={13} />
                  </button>
                ))}
              </div>
              <div className={s.clusterActions}>
                <button className={s.textButton} onClick={() => onOpen(c.cluster_id, 'nodes')}>
                  Участники <ArrowRight size={15} />
                </button>
                <button className={s.secondaryButton} onClick={() => onOpen(c.cluster_id, 'graph')}>
                  <NetworkIcon size={15} />
                  На графе
                </button>
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}

function ResilienceView({ data }: { data: Dataset }) {
  const [selected, setSelected] = useState(10);
  const rows = data.resilience;
  const active = rows.find((r) => r.removed_top_n === selected) || rows[0];
  if (!active) return <Empty>Расчёт устойчивости отсутствует в выгрузке.</Empty>;
  const x = (i: number) => 65 + i * 130;
  const y = (value: number) => 235 - value * 190;
  const points = rows.map((r, i) => `${x(i)},${y(r.reachable_share)}`).join(' ');
  return (
    <>
      <div className={s.infoBanner}>
        <ShieldCheck size={19} />
        <span>
          Сценарии моделируют изъятие узлов по текущему рейтингу приоритета. Это оценка структуры, а
          не прогноз поведения клиентов.
        </span>
      </div>
      <div className={s.scenarios}>
        <strong>Изъять из сети</strong>
        {rows.map((r) => (
          <button
            key={r.removed_top_n}
            className={selected === r.removed_top_n ? s.scenarioActive : ''}
            onClick={() => setSelected(r.removed_top_n)}
          >
            {r.removed_top_n === 0 ? 'Ни одного' : `Топ-${r.removed_top_n}`}
          </button>
        ))}
      </div>
      <div className={s.metrics}>
        <Metric
          icon={<GitBranch size={19} />}
          label="Отрезано от seed"
          value={percent(1 - active.reachable_share)}
          note="Доля узлов, потерявших достижимость"
        />
        <Metric
          icon={<Users size={19} />}
          label="Остаются достижимыми"
          value={number(active.reachable_from_seeds)}
          note={`Из ${number(data.summary.n_nodes)} участников`}
        />
        <Metric
          icon={<Layers size={19} />}
          label="Компоненты сети"
          value={number(active.components)}
          note="Отдельные части после изъятия"
        />
        <Metric
          icon={<Wallet size={19} />}
          label="Затронутый оборот"
          value={percent(active.flow_removed_share)}
          note={money(active.flow_removed_kzt)}
        />
      </div>
      <section className={s.card}>
        <div className={s.cardHeading}>
          <div>
            <h2>Достижимость от исходных клиентов</h2>
            <p>Доля участников, до которых остаётся путь от seed</p>
          </div>
          <span className={s.chartKey}>
            <i />
            Достижимые узлы
          </span>
        </div>
        <div className={s.chartContainer}>
          <svg
            viewBox="0 0 780 290"
            role="img"
            aria-label="Доля достижимых узлов уменьшается при изъятии приоритетных участников; точные значения в таблице ниже."
          >
            <defs>
              <linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#2563eb" stopOpacity=".16" />
                <stop offset="100%" stopColor="#2563eb" stopOpacity=".01" />
              </linearGradient>
            </defs>
            {[0, 0.25, 0.5, 0.75, 1].map((v) => (
              <g key={v}>
                <line x1="65" y1={y(v)} x2="715" y2={y(v)} stroke="#e8edf3" strokeDasharray="4 4" />
                <text x="50" y={y(v) + 4} textAnchor="end" fill="#8491a5" fontSize="11">
                  {v * 100}%
                </text>
              </g>
            ))}
            <polygon points={`65,235 ${points} ${x(rows.length - 1)},235`} fill="url(#chartFill)" />
            <polyline
              points={points}
              fill="none"
              stroke="#2563eb"
              strokeWidth="3"
              strokeLinejoin="round"
            />
            {rows.map((r, i) => (
              <g key={r.removed_top_n}>
                <circle
                  cx={x(i)}
                  cy={y(r.reachable_share)}
                  r={selected === r.removed_top_n ? 7 : 4}
                  fill="#fff"
                  stroke="#2563eb"
                  strokeWidth="3"
                />
                <text x={x(i)} y="265" textAnchor="middle" fill="#64748b" fontSize="12">
                  {r.removed_top_n === 0 ? 'Исходная сеть' : `Топ-${r.removed_top_n}`}
                </text>
              </g>
            ))}
          </svg>
        </div>
        <div className={s.tableScroll}>
          <table>
            <thead>
              <tr>
                <th>Сценарий</th>
                <th>Отрезано от seed</th>
                <th>Достижимые узлы</th>
                <th>Компоненты</th>
                <th>Крупнейшая компонента</th>
                <th>Затронутый оборот</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.removed_top_n}
                  className={selected === r.removed_top_n ? s.highlightRow : ''}
                >
                  <td>
                    <button className={s.gidButton} onClick={() => setSelected(r.removed_top_n)}>
                      {r.removed_top_n ? `Топ-${r.removed_top_n}` : 'Исходная сеть'}
                    </button>
                  </td>
                  <td>{percent(1 - r.reachable_share)}</td>
                  <td>{number(r.reachable_from_seeds)}</td>
                  <td>{number(r.components)}</td>
                  <td>{number(r.largest_component)}</td>
                  <td>{money(r.flow_removed_kzt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function NodeCard({
  data,
  node,
  gid,
  onClose,
  onSelect,
  onGraph,
  onCluster,
  inline = false,
}: {
  data: Dataset;
  node?: GraphNode;
  gid: string;
  onClose: () => void;
  onSelect: (gid: string) => void;
  onGraph: (gid: string) => void;
  onCluster: (id: number) => void;
  inline?: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  useEffect(() => {
    if (inline) return;
    const before = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeRef.current();
      if (e.key === 'Tab') {
        const focusable = ref.current?.querySelectorAll<HTMLElement>(
          'button, a[href], [tabindex="0"]',
        );
        if (!focusable?.length) return;
        const first = focusable[0],
          last = focusable[focusable.length - 1];
        if (
          e.shiftKey &&
          (document.activeElement === first || document.activeElement === ref.current)
        ) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', handler);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handler);
      document.body.style.overflow = overflow;
      before?.focus();
    };
  }, [inline]);
  const incoming = data.edges
    .filter((e) => e.dst === gid)
    .sort((a, b) => b.sum_kzt - a.sum_kzt)
    .slice(0, 6);
  const outgoing = data.edges
    .filter((e) => e.src === gid)
    .sort((a, b) => b.sum_kzt - a.sum_kzt)
    .slice(0, 6);
  return (
    <div
      className={inline ? s.inlineCard : s.drawerBackdrop}
      onClick={inline ? undefined : onClose}
    >
      <aside
        ref={ref}
        tabIndex={-1}
        className={s.drawer}
        role={inline ? 'region' : 'dialog'}
        aria-modal={inline ? undefined : true}
        aria-labelledby="node-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={s.drawerHeader}>
          <span>
            <Users size={18} />
            Карточка участника
          </span>
          <button className={s.iconButton} onClick={onClose} aria-label="Закрыть карточку">
            <X size={21} />
          </button>
        </div>
        {!node ? (
          <div className={s.drawerBody}>
            <h2 id="node-title">Узел не найден</h2>
            <p className={s.mono}>{gid}</p>
            <p>Такого идентификатора нет в текущей выгрузке.</p>
          </div>
        ) : (
          <div className={s.drawerBody}>
            <div className={s.miniLabel}>
              ИДЕНТИФИКАТОР УЗЛА {node.is_seed && <span className={s.seedLabel}>SEED</span>}
            </div>
            <div className={s.nodeTitle}>
              <h2 id="node-title">{gid}</h2>
              <button
                className={s.iconButton}
                aria-label="Копировать gid"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(gid);
                    setCopied(true);
                    setCopyError(false);
                  } catch {
                    setCopyError(true);
                  }
                }}
              >
                {copied ? <Check size={17} /> : <Copy size={17} />}
              </button>
            </div>
            {copied && (
              <p className={s.copyStatus} role="status">
                gid скопирован
              </p>
            )}
            {copyError && (
              <p role="status">Копирование недоступно. Выделите идентификатор вручную.</p>
            )}
            <RoleBadge role={node.role} data={data} />
            <div className={s.nodeScores}>
              <div>
                <span>Приоритет проверки</span>
                <strong>{score(node.priority_score)}</strong>
              </div>
              <div>
                <span>Уверенность в роли</span>
                <strong>{percent(node.role_score)}</strong>
              </div>
            </div>
            <div className={s.evidence}>
              <div>
                <ListFilter size={16} />
                <strong>Основание гипотезы</strong>
              </div>
              <p>{node.evidence}</p>
            </div>
            {node.depth_truncated && (
              <div className={s.warning}>
                <AlertTriangle size={19} />
                <p>
                  Обход остановлен на 4-м колене. Отсутствие исходящих переводов не подтверждает,
                  что деньги остались у этого участника.
                </p>
              </div>
            )}
            {node.is_seed && (
              <div className={s.warning}>
                <CircleHelp size={19} />
                <p>Входящие переводы seed могут быть неполными: выгрузка построена по исходящим.</p>
              </div>
            )}
            <button className={`${s.primaryButton} ${s.fullWidth}`} onClick={() => onGraph(gid)}>
              <NetworkIcon size={17} />
              {inline ? 'Сделать центром графа' : 'Показать окружение на графе'}
              <ArrowUpRight size={17} />
            </button>
            <h3 className={s.drawerSection}>Денежные потоки</h3>
            <div className={s.flowCards}>
              <div>
                <span>
                  <ArrowDownLeft size={17} />
                  Входящие
                </span>
                <strong>{money(node.in_kzt)}</strong>
                <small>
                  {number(node.in_deg)} плательщиков · {number(node.in_tx)} переводов
                </small>
              </div>
              <div>
                <span>
                  <ArrowUpRight size={17} />
                  Исходящие
                </span>
                <strong>{money(node.out_kzt)}</strong>
                <small>
                  {number(node.out_deg)} получателей · {number(node.out_tx)} переводов
                </small>
              </div>
            </div>
            <dl className={s.details}>
              <div>
                <dt>Кластер</dt>
                <dd>
                  <button className={s.textButton} onClick={() => onCluster(node.cluster_id)}>
                    #{node.cluster_id}
                    <ArrowUpRight size={13} />
                  </button>
                </dd>
              </div>
              <div>
                <dt>Колено обхода</dt>
                <dd>{node.depth}</dd>
              </div>
              <div>
                <dt>Доходят средства от seed</dt>
                <dd>{node.seed_sources}</dd>
              </div>
              <div>
                <dt>Коэффициент пропуска</dt>
                <dd>{node.pass_through === null ? '—' : node.pass_through.toFixed(2)}</dd>
              </div>
              <div>
                <dt>Посредничество</dt>
                <dd>{node.betweenness.toFixed(5)}</dd>
              </div>
              <div>
                <dt>Встречные счета</dt>
                <dd>{node.reciprocal_partners}</dd>
              </div>
              <div>
                <dt>Минимальная длина цикла</dt>
                <dd>{node.min_cycle_len || 'Нет циклов'}</dd>
              </div>
              <div>
                <dt>Точка сочленения</dt>
                <dd>{node.is_articulation ? 'Да' : 'Нет'}</dd>
              </div>
            </dl>
            {[
              [incoming, 'Крупнейшие входящие', 'src'],
              [outgoing, 'Крупнейшие исходящие', 'dst'],
            ].map(([edges, title, field]) => (
              <div key={String(title)}>
                <h3 className={s.drawerSection}>{String(title)}</h3>
                {(edges as typeof incoming).length ? (
                  (edges as typeof incoming).map((e) => (
                    <button
                      key={`${e.src}-${e.dst}`}
                      className={s.counterparty}
                      onClick={() => onSelect(e[field as 'src' | 'dst'])}
                    >
                      <span>{e[field as 'src' | 'dst']}</span>
                      <strong>{money(e.sum_kzt)}</strong>
                      <ChevronRight size={15} />
                    </button>
                  ))
                ) : (
                  <p className={s.muted}>В выгрузке нет таких переводов.</p>
                )}
              </div>
            ))}
            <p className={s.footnote}>
              Выводы ограничены внутрибанковскими переводами от 5 000 ₸ и глубиной обхода.
            </p>
          </div>
        )}
      </aside>
    </div>
  );
}
