import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowRight,
  Bot,
  Braces,
  CircleDot,
  Database,
  Eye,
  GitBranch,
  MessageSquareText,
  Radar,
  Sparkles,
  Users,
} from "lucide-react";
import demoData from "./data/demoData.json";
import "./styles.css";

const percent = (value) => `${Math.round(value * 1000) / 10}%`;

function Metric({ icon: Icon, label, value, accent }) {
  return (
    <div className="metric" style={{ "--accent": accent }}>
      <Icon size={18} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function FlowStep({ icon: Icon, title, text }) {
  return (
    <div className="flow-step">
      <Icon size={19} />
      <div>
        <strong>{title}</strong>
        <span>{text}</span>
      </div>
    </div>
  );
}

function PairRow({ pair, active, onSelect }) {
  return (
    <button className={`pair-row ${active ? "active" : ""}`} onClick={() => onSelect(pair)}>
      <span className="rank">#{pair.rank}</span>
      <span className="pair-names">
        <strong>{pair.userA.name}</strong>
        <ArrowRight size={15} />
        <strong>{pair.userB.name}</strong>
      </span>
      <span className="gravity">{percent(pair.gravity)}</span>
    </button>
  );
}

function UserPanel({ user, side }) {
  return (
    <section className="user-panel">
      <div className="user-heading">
        <span className={`avatar ${side}`}>{user.name.slice(0, 1).toUpperCase()}</span>
        <div>
          <h2>{user.name}</h2>
          <p>{user.postCount} 帖 · {user.commentCount} 评论 · {user.totalLikes} 赞</p>
        </div>
      </div>
      <div className="tags">
        {user.tags.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      <div className="samples">
        {user.samples.length ? (
          user.samples.map((sample, index) => <p key={index}>{sample}</p>)
        ) : (
          <p>样本内容不足，等待下一轮采集补全画像。</p>
        )}
      </div>
    </section>
  );
}

function NetworkMap({ pairs, selectedId, onSelect }) {
  const nodes = useMemo(() => {
    const seen = new Map();
    pairs.slice(0, 9).forEach((pair) => {
      if (!seen.has(pair.userA.name)) seen.set(pair.userA.name, { name: pair.userA.name });
      if (!seen.has(pair.userB.name)) seen.set(pair.userB.name, { name: pair.userB.name });
    });
    return Array.from(seen.values()).slice(0, 12).map((node, index, list) => {
      const angle = (Math.PI * 2 * index) / list.length - Math.PI / 2;
      const radius = index % 3 === 0 ? 34 : 42;
      return {
        ...node,
        x: 50 + Math.cos(angle) * radius,
        y: 50 + Math.sin(angle) * radius,
      };
    });
  }, [pairs]);

  const getNode = (name) => nodes.find((node) => node.name === name);

  return (
    <svg className="network" viewBox="0 0 100 100" role="img" aria-label="隐藏同好引力网络图">
      <defs>
        <filter id="soft-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="1.4" floodOpacity="0.22" />
        </filter>
      </defs>
      {pairs.slice(0, 9).map((pair) => {
        const a = getNode(pair.userA.name);
        const b = getNode(pair.userB.name);
        if (!a || !b) return null;
        const selected = pair.id === selectedId;
        return (
          <g key={pair.id} onClick={() => onSelect(pair)} className="edge-group">
            <line
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              className={selected ? "edge selected" : "edge"}
              strokeWidth={selected ? 1.4 : Math.max(0.35, pair.gravity)}
            />
          </g>
        );
      })}
      {nodes.map((node, index) => (
        <g key={node.name} filter="url(#soft-shadow)">
          <circle cx={node.x} cy={node.y} r={index < 4 ? 3.8 : 3.1} className="node" />
          <text x={node.x} y={node.y + 6.6} textAnchor="middle">
            {node.name.length > 5 ? `${node.name.slice(0, 5)}…` : node.name}
          </text>
        </g>
      ))}
    </svg>
  );
}

function App() {
  const [selected, setSelected] = useState(demoData.pairs[0]);

  return (
    <main>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow"><Sparkles size={16} /> 知乎黑客松 Demo</span>
          <h1>引力拓扑</h1>
          <p>
            用社区内容和互动数据，发现那些观点相似、气质接近、但还没有真正碰面的隐藏同好。
            Agent 先替他们进行一次低打扰对话预演，再生成连接建议报告。
          </p>
        </div>
        <div className="hero-visual">
          <NetworkMap pairs={demoData.pairs} selectedId={selected.id} onSelect={setSelected} />
        </div>
      </section>

      <section className="metrics-grid" aria-label="数据概览">
        <Metric icon={Users} label="采集用户" value={demoData.stats.users} accent="#2f6df6" />
        <Metric icon={Database} label="社区帖子" value={demoData.stats.posts} accent="#d46731" />
        <Metric icon={MessageSquareText} label="评论样本" value={demoData.stats.comments} accent="#1f9d78" />
        <Metric icon={GitBranch} label="隐藏同好" value={demoData.stats.hiddenPairs} accent="#8f54c7" />
      </section>

      <section className="workspace">
        <aside className="leaderboard" aria-label="隐藏同好排行榜">
          <div className="section-title">
            <Radar size={18} />
            <h2>隐藏同好榜</h2>
          </div>
          <div className="pair-list">
            {demoData.pairs.map((pair) => (
              <PairRow
                key={pair.id}
                pair={pair}
                active={pair.id === selected.id}
                onSelect={setSelected}
              />
            ))}
          </div>
        </aside>

        <section className="report" aria-label="引力探测报告">
          <div className="report-head">
            <div>
              <span className="eyebrow"><Eye size={15} /> 探测报告 #{selected.rank}</span>
              <h2>{selected.userA.name} × {selected.userB.name}</h2>
            </div>
            <div className="score">
              <span>引力值</span>
              <strong>{percent(selected.gravity)}</strong>
            </div>
          </div>

          <div className="tag-line">
            {selected.sharedTags.map((tag) => <span key={tag}>{tag}</span>)}
          </div>

          <p className="insight">{selected.insight}</p>

          <div className="user-grid">
            <UserPanel user={selected.userA} side="left" />
            <UserPanel user={selected.userB} side="right" />
          </div>

          <section className="dialogue">
            <div className="section-title">
              <Bot size={18} />
              <h2>A2A 对话预演</h2>
            </div>
            {selected.conversation.map((line, index) => (
              <div className="dialogue-line" key={`${line.speaker}-${index}`}>
                <span>{line.speaker}</span>
                <p>{line.text}</p>
              </div>
            ))}
          </section>
        </section>
      </section>

      <section className="flow" aria-label="系统流程">
        <FlowStep icon={Database} title="采集" text="读取圈子帖子、评论、互动关系，构建用户内容样本。" />
        <FlowStep icon={Braces} title="计量" text="用文本相似度与互动排除，找出高引力但未互动的用户对。" />
        <FlowStep icon={Activity} title="预演" text="实例化双方 Agent，用历史内容生成一次对话模拟。" />
        <FlowStep icon={CircleDot} title="连接" text="输出可解释的引力报告，给真人一个低压力开场。" />
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
