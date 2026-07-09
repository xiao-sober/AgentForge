import { useEffect, useState, type ReactNode } from "react";
import { getJson } from "../../api";
import { formatBeijingShort } from "../../datetime";
import type { I18nKey } from "../../i18n";
import type { JsonRecord, MemoryEpisodeRecord, SemanticMemoryRecord } from "../../types";

interface MemoryViewProps {
  active: boolean;
  t: (key: I18nKey) => string;
}

export function MemoryView({ active, t }: MemoryViewProps) {
  const [episodes, setEpisodes] = useState<MemoryEpisodeRecord[]>([]);
  const [semanticMemory, setSemanticMemory] = useState<SemanticMemoryRecord[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadMemory = async (search = query.trim()) => {
    setLoading(true);
    setError("");
    const suffix = search ? `?q=${encodeURIComponent(search)}&limit=50` : "?limit=50";
    try {
      const [episodePayload, semanticPayload] = await Promise.all([
        getJson<{ episodes?: MemoryEpisodeRecord[] }>(`/memory/episodes${suffix}`),
        getJson<{ semantic_memory?: SemanticMemoryRecord[] }>(`/memory/semantic${suffix}`)
      ]);
      setEpisodes(episodePayload.episodes || []);
      setSemanticMemory(semanticPayload.semantic_memory || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (active) {
      void loadMemory("");
    }
  }, [active]);

  return (
    <section className={active ? "memory-workbench active" : "memory-workbench"}>
      <div className="runs-head">
        <div>
          <h2>{t("memory")}</h2>
          <p>{t("memorySubtitle")}</p>
        </div>
        <button className="secondary" type="button" onClick={() => void loadMemory()}>
          {loading ? t("loading") : t("refresh")}
        </button>
      </div>

      <div className="memory-controls">
        <div className="memory-toolbar">
          <label htmlFor="memoryQuery">{t("query")}</label>
          <input
            id="memoryQuery"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void loadMemory();
              }
            }}
          />
          <button type="button" onClick={() => void loadMemory()}>
            {t("search")}
          </button>
        </div>

        {error ? <div className="inline-error compact">{error}</div> : null}
      </div>

      <div className="memory-grid">
        <MemoryColumn title={t("latestEpisodes")} count={episodes.length} emptyText={t("noEpisodes")}>
          {episodes.map((episode, index) => (
            <article className="memory-row" key={episode.episode_id || `${episode.created_at || "episode"}-${index}`}>
              <div>
                <strong>{episode.user_input || episode.episode_id || t("episode")}</strong>
                <time>{formatBeijingShort(episode.created_at)}</time>
              </div>
              <p>{truncate(String(episode.response || episode.summary || "-"), 220)}</p>
              <MemoryMeta record={episode} />
            </article>
          ))}
        </MemoryColumn>

        <MemoryColumn title={t("semanticMemory")} count={semanticMemory.length} emptyText={t("noSemanticMemory")}>
          {semanticMemory.map((record, index) => (
            <article className="memory-row" key={record.key || `${record.updated_at || "semantic"}-${index}`}>
              <div>
                <strong>{record.key || t("semantic")}</strong>
                <time>{formatBeijingShort(record.updated_at)}</time>
              </div>
              <p>{truncate(String(record.summary || record.description || record.purpose || "-"), 220)}</p>
              <MemoryMeta record={record} />
            </article>
          ))}
        </MemoryColumn>
      </div>
    </section>
  );
}

function MemoryColumn({
  title,
  count,
  emptyText,
  children
}: {
  title: string;
  count: number;
  emptyText: string;
  children: ReactNode;
}) {
  return (
    <section className="memory-column">
      <div className="section-heading">
        <h3>{title}</h3>
        <span className="badge">{count}</span>
      </div>
      {count ? children : <p className="muted-text">{emptyText}</p>}
    </section>
  );
}

function MemoryMeta({ record }: { record: JsonRecord }) {
  const score = typeof record._memory_score === "number" ? record._memory_score.toFixed(2) : "";
  const reasons = Array.isArray(record._memory_reasons) ? record._memory_reasons.slice(0, 3).join(", ") : "";
  const tags = Array.isArray(record.tags) ? record.tags.slice(0, 4).map(String).join(", ") : "";
  const meta = [score ? `score ${score}` : "", reasons, tags].filter(Boolean).join(" · ");
  return meta ? <small>{meta}</small> : null;
}

function truncate(value: string, maxLength: number): string {
  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}...` : value;
}
