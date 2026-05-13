import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dataPath = join(root, "zhihu_data_full.json");
const pairsPath = join(root, "gravity_results_optimized.json");
const outPath = join(root, "src", "data", "demoData.json");

const readJson = async (path) => JSON.parse(await readFile(path, "utf8"));

const truncate = (value = "", length = 96) => {
  const text = String(value).replace(/\s+/g, " ").trim();
  return text.length > length ? `${text.slice(0, length)}...` : text;
};

const inferTags = (texts) => {
  const joined = texts.join(" ");
  const dictionary = [
    ["AI", ["AI", "大模型", "模型", "agent", "Agent", "智能体"]],
    ["技术系统", ["系统", "算法", "数据", "代码", "开发", "API"]],
    ["社区观察", ["社区", "圈子", "互动", "用户", "连接", "关系"]],
    ["表达实验", ["故事", "写作", "表达", "创作", "叙事"]],
    ["哲学思考", ["哲学", "意义", "存在", "伦理", "人文"]],
  ];

  const tags = dictionary
    .filter(([, words]) => words.some((word) => joined.includes(word)))
    .map(([label]) => label);

  return tags.length ? tags.slice(0, 3) : ["潜在同频", "内容相似"];
};

const pickUser = (users, tokenOrName) => {
  if (users[tokenOrName]) return users[tokenOrName];
  return Object.values(users).find((user) => user.name === tokenOrName || user.token === tokenOrName);
};

const summarizeUser = (users, tokenOrName) => {
  const user = pickUser(users, tokenOrName);
  if (!user) {
    return {
      token: tokenOrName,
      name: tokenOrName,
      postCount: 0,
      commentCount: 0,
      totalLikes: 0,
      tags: ["样本待补全"],
      samples: [],
    };
  }

  const texts = (user.contents || []).filter(Boolean);
  return {
    token: user.token || tokenOrName,
    name: user.name || tokenOrName,
    postCount: user.post_count || 0,
    commentCount: user.comment_count || 0,
    totalLikes: user.total_likes || 0,
    tags: inferTags(texts),
    samples: texts.slice(0, 3).map((text) => truncate(text, 110)),
  };
};

const buildConversation = (pair, userA, userB) => {
  const firstA = userA.samples[0] || "我更关心一个连接为什么成立，而不只是分数有多高。";
  const firstB = userB.samples[0] || "如果系统能解释相似之处，陌生人之间的第一句话会更自然。";

  return [
    {
      speaker: userA.name,
      text: `我从自己的内容里看到一个线索：${firstA} 这类问题不是简单推荐，而是要解释我们为什么可能聊得来。`,
    },
    {
      speaker: userB.name,
      text: `我接得上这个方向。${firstB} 如果引力值是 ${(pair.gravity * 100).toFixed(1)}%，我更想知道共同语境在哪里。`,
    },
    {
      speaker: userA.name,
      text: `共同语境大概是“${userA.tags[0]}”和“${userB.tags[0]}”的交叉点。先由 Agent 预演一次，再把低打扰的连接建议交给真人。`,
    },
  ];
};

const main = async () => {
  const [data, pairResults] = await Promise.all([readJson(dataPath), readJson(pairsPath)]);
  const pairs = pairResults.hidden_pairs.slice(0, 12).map((pair, index) => {
    const userA = summarizeUser(data.users, pair.user_a);
    const userB = summarizeUser(data.users, pair.user_b);
    return {
      id: `pair-${index + 1}`,
      rank: index + 1,
      gravity: pair.gravity,
      userA,
      userB,
      sharedTags: [...new Set([...userA.tags, ...userB.tags])].slice(0, 4),
      insight: `${userA.name} 和 ${userB.name} 在内容气质上高度接近，但采集到的数据里没有直接互动记录。`,
      conversation: buildConversation(pair, userA, userB),
    };
  });

  const output = {
    generatedAt: new Date().toISOString(),
    stats: {
      users: Object.keys(data.users || {}).length,
      posts: (data.posts || []).length,
      comments: (data.comments || []).length,
      hiddenPairs: pairResults.total_pairs || pairResults.hidden_pairs.length,
      filteredUsers: pairResults.filtered_user_count || 0,
    },
    rings: [
      "OpenClaw 人类观察员",
      "A2A for Reconnect",
      "黑客松脑洞补给站",
    ],
    pairs,
  };

  await mkdir(dirname(outPath), { recursive: true });
  await writeFile(outPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  console.log(`Demo data written: ${outPath}`);
};

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
