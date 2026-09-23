import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import cytoscape, { type Core, type ElementDefinition, type Position } from 'cytoscape';
import type { Edge } from './types';
import type { GraphModel } from './graph';
import { money } from './data';
import g from './Network.module.css';

export interface CanvasControls {
  fit: () => void;
  center: () => void;
  zoom: (factor: number) => void;
  reset: () => void;
}
interface SavedView {
  positions: Map<string, Position>;
  zoom?: number;
  pan?: Position;
}
interface Props {
  model: GraphModel;
  viewKey: string;
  focus: string;
  selected: string;
  selectedEdge: string;
  onNode: (id: string) => void;
  onEdge: (edge: Edge) => void;
}
const GraphCanvas = forwardRef<CanvasControls, Props>(function GraphCanvas(props, ref) {
  const container = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const viewKey = useRef('');
  const views = useRef(new Map<string, SavedView>());
  const [tip, setTip] = useState('');

  const save = () => {
    const instance = cy.current;
    if (!instance || !viewKey.current) return;
    const view = views.current.get(viewKey.current) || { positions: new Map<string, Position>() };
    instance.nodes().forEach((n) => {
      view.positions.set(n.id(), { ...n.position() });
    });
    view.zoom = instance.zoom();
    view.pan = { ...instance.pan() };
    views.current.set(viewKey.current, view);
  };
  useImperativeHandle(ref, () => ({
    fit: () => {
      cy.current?.fit(undefined, 50);
      save();
    },
    center: () => {
      const n = cy.current?.getElementById(latest.current.selected || latest.current.focus);
      if (n?.length) cy.current?.center(n);
      save();
    },
    zoom: (factor) => {
      const instance = cy.current;
      if (instance)
        instance.zoom({
          level: instance.zoom() * factor,
          renderedPosition: { x: instance.width() / 2, y: instance.height() / 2 },
        });
      save();
    },
    reset: () => {
      const instance = cy.current;
      if (!instance) return;
      views.current.delete(viewKey.current);
      instance.nodes().positions((n) => {
        const node = latest.current.model.nodes.find((item) => item.id === n.id())!;
        return { x: node.x, y: node.y };
      });
      instance.fit(undefined, 50);
      save();
    },
  }));

  useEffect(() => {
    if (!container.current) return;
    const instance = cytoscape({
      container: container.current,
      minZoom: 0.1,
      maxZoom: 3,
      wheelSensitivity: 0.2,
      layout: { name: 'preset' },
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            shape: (n) => n.data('shape'),
            width: 'data(width)',
            height: 'data(size)',
            label: 'data(label)',
            'font-family': 'system-ui',
            'font-size': 13,
            color: '#405575',
            'font-weight': 500,
            'text-valign': 'bottom',
            'text-margin-y': 8,
            'text-wrap': 'wrap',
            'text-background-color': '#fff',
            'text-background-opacity': 0.9,
            'text-background-padding': '3px',
            'border-width': 2,
            'border-color': '#fff',
          },
        },
        {
          selector: 'node[?cluster]',
          style: {
            'text-valign': 'center',
            color: '#fff',
            'font-size': 12,
            'text-margin-y': 0,
            'text-background-opacity': 0,
            'text-outline-width': 0,
          },
        },
        { selector: 'node[?seed]', style: { 'border-width': 3, 'border-color': '#23395d' } },
        { selector: 'node[?context]', style: { opacity: 0.55 } },
        {
          selector: 'node.focus',
          style: { 'border-width': 4, 'border-color': '#1d4ed8', 'font-weight': 700 },
        },
        {
          selector: 'node.selected',
          style: { 'border-width': 5, 'border-color': '#06b6d4', opacity: 1, 'z-index': 10 },
        },
        {
          selector: 'edge',
          style: {
            width: 'data(width)',
            'line-color': '#a9bbd3',
            'target-arrow-color': '#809abc',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 1,
            'curve-style': 'bezier',
            'control-point-step-size': 50,
            opacity: 0.6,
          },
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#2563eb',
            'target-arrow-color': '#2563eb',
            opacity: 1,
            width: 2.5,
            'z-index': 11,
          },
        },
        { selector: 'edge.dim', style: { opacity: 0.12 } },
        { selector: 'node.dim', style: { opacity: 0.35 } },
        {
          selector: 'edge.selected',
          style: {
            'line-color': '#0891b2',
            'target-arrow-color': '#0891b2',
            opacity: 1,
            width: 4,
            'z-index': 12,
          },
        },
        {
          selector: 'edge.amount',
          style: {
            label: 'data(amount)',
            'font-size': 12,
            color: '#28548c',
            'text-rotation': 'autorotate',
            'text-background-color': '#fff',
            'text-background-opacity': 1,
            'text-background-padding': '4px',
          },
        },
      ],
    });
    cy.current = instance;
    instance.on('tap', 'node', (e) => latest.current.onNode(e.target.id()));
    instance.on('tap', 'edge', (e) => {
      const edge = latest.current.model.edges.find(
        (edge) => `${edge.src}>${edge.dst}` === e.target.id(),
      );
      if (edge) latest.current.onEdge(edge);
    });
    instance.on('mouseover', 'node', (e) => {
      setTip(e.target.data('gid') || e.target.data('label').replace('\n', ' · '));
    });
    instance.on('mouseover', 'edge', (e) =>
      setTip(`${e.target.data('amount')} · ${e.target.data('transactions')} переводов`),
    );
    instance.on('mouseout', 'node, edge', () => setTip(''));
    instance.on('dragfree pan zoom', save);
    const resize = new ResizeObserver(() => instance.resize());
    resize.observe(container.current);
    return () => {
      save();
      resize.disconnect();
      instance.destroy();
      cy.current = null;
      viewKey.current = '';
    };
  }, []);

  useEffect(() => {
    const instance = cy.current;
    if (!instance) return;
    save();
    const changingView = props.viewKey !== viewKey.current;
    const saved = views.current.get(props.viewKey);
    viewKey.current = props.viewKey;
    const ids = new Set([
      ...props.model.nodes.map((n) => n.id),
      ...props.model.edges.map((e) => `${e.src}>${e.dst}`),
    ]);
    const elements: ElementDefinition[] = props.model.nodes.map((n) => ({
      data: {
        id: n.id,
        gid: n.gid,
        label: n.label,
        color: n.color,
        shape: n.shape,
        width: n.clusterId === undefined ? n.size : 130 + n.size * 0.65,
        size: n.clusterId === undefined ? n.size : 40 + n.size * 0.45,
        cluster: n.clusterId !== undefined,
        seed: n.seed && n.clusterId === undefined,
        context: n.context,
      },
      position: saved?.positions.get(n.id) || { x: n.x, y: n.y },
    }));
    for (const e of props.model.edges)
      elements.push({
        data: {
          id: `${e.src}>${e.dst}`,
          source: e.src,
          target: e.dst,
          amount: money(e.sum_kzt),
          transactions: e.n_tx,
          width: Math.max(1, Math.min(4, Math.log10(Math.max(1, e.sum_kzt)) / 2)),
        },
      });
    instance.batch(() => {
      if (changingView) instance.elements().remove();
      else
        instance
          .elements()
          .filter((e) => !ids.has(e.id()))
          .remove();
      for (const element of elements) {
        const present = instance.getElementById(element.data.id!);
        if (present.length) present.data(element.data);
        else instance.add(element);
      }
    });
    if (changingView) {
      if (saved?.zoom !== undefined && saved.pan) {
        instance.zoom(saved.zoom);
        instance.pan(saved.pan);
      } else if (instance.nodes().length) {
        const nearby = instance
          .nodes()
          .filter((n) => Math.abs(n.position('x')) <= 340 && Math.abs(n.position('y')) <= 350);
        instance.fit(props.viewKey.startsWith('node:') && nearby.length ? nearby : undefined, 50);
      }
    }
    save();
  }, [props.model, props.viewKey]);

  useEffect(() => {
    const instance = cy.current;
    if (!instance) return;
    instance.elements().removeClass('focus selected highlighted amount dim');
    instance.getElementById(props.focus).addClass('focus');
    const selected = instance.getElementById(props.selected);
    selected.addClass('selected');
    const neighbors = selected.connectedEdges();
    neighbors.addClass('highlighted');
    if (props.viewKey === 'clusters' && selected.length) {
      instance.elements().difference(selected.closedNeighborhood()).addClass('dim');
    }
    if (neighbors.length <= 8) neighbors.addClass('amount');
    instance.getElementById(props.selectedEdge).addClass('selected amount');
  }, [props.selected, props.selectedEdge, props.focus, props.model]);

  return (
    <div className={g.canvasWrap}>
      <div
        ref={container}
        className={g.canvas}
        role="img"
        aria-label="Интерактивный граф денежных переводов"
      />
      {tip && (
        <div className={g.tooltip} role="status">
          {tip}
        </div>
      )}
      {!props.model.nodes.length && (
        <div className={g.empty}>Нет участников, подходящих под условия.</div>
      )}
    </div>
  );
});

export default GraphCanvas;
