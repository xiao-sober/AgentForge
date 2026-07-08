import { useEffect, useMemo, useState } from "react";
import { getJson } from "../../api";
import type { I18nKey } from "../../i18n";
import type { JsonRecord, SkillSummary, SkillVersionRecord } from "../../types";

interface SkillsViewProps {
  active: boolean;
  t: (key: I18nKey) => string;
}

export function SkillsView({ active, t }: SkillsViewProps) {
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [selectedSkillSlug, setSelectedSkillSlug] = useState("");
  const [selectedVersion, setSelectedVersion] = useState("");
  const [versionDetail, setVersionDetail] = useState<SkillVersionRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const selectedSkill = useMemo(
    () => skills.find((skill) => skill.skill_slug === selectedSkillSlug) || skills[0] || null,
    [selectedSkillSlug, skills]
  );

  async function loadSkills() {
    setLoading(true);
    setError("");
    try {
      const payload = await getJson<{ skills?: SkillSummary[] }>("/skills");
      const nextSkills = payload.skills || [];
      setSkills(nextSkills);
      setSelectedSkillSlug((current) =>
        current && nextSkills.some((skill) => skill.skill_slug === current) ? current : nextSkills[0]?.skill_slug || ""
      );
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (active) {
      void loadSkills();
    }
  }, [active]);

  useEffect(() => {
    if (!selectedSkill) {
      setSelectedVersion("");
      return;
    }
    const versions = selectedSkill.versions || [];
    setSelectedVersion((current) =>
      current && versions.includes(current) ? current : selectedSkill.latest_version || versions[0] || ""
    );
  }, [selectedSkill]);

  useEffect(() => {
    let cancelled = false;
    async function loadVersion() {
      if (!selectedSkill || !selectedVersion) {
        setVersionDetail(null);
        return;
      }
      try {
        const payload = await getJson<SkillVersionRecord>(
          `/skills/${encodeURIComponent(selectedSkill.skill_slug)}/${encodeURIComponent(selectedVersion)}`
        );
        if (!cancelled) {
          setVersionDetail(payload);
        }
      } catch (loadError) {
        if (!cancelled) {
          setVersionDetail(null);
          setError(loadError instanceof Error ? loadError.message : String(loadError));
        }
      }
    }
    if (active) {
      void loadVersion();
    }
    return () => {
      cancelled = true;
    };
  }, [active, selectedSkill?.skill_slug, selectedVersion]);

  return (
    <section className={active ? "catalog-workbench active" : "catalog-workbench"}>
      <div className="runs-head">
        <div>
          <h2>{t("skills")}</h2>
          <p>{t("skillsSubtitle")}</p>
        </div>
        <button className="secondary" type="button" onClick={() => void loadSkills()}>
          {loading ? t("loading") : t("refresh")}
        </button>
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <div className="catalog-layout">
        <div className="catalog-list" aria-label={t("skills")}>
          {skills.length ? (
            skills.map((skill) => (
              <button
                className={skill.skill_slug === selectedSkill?.skill_slug ? "catalog-row active" : "catalog-row"}
                key={skill.skill_slug}
                type="button"
                onClick={() => setSelectedSkillSlug(skill.skill_slug)}
              >
                <strong>{skill.title || skill.skill_slug}</strong>
                <span>{skill.skill_slug}</span>
                <small>{skill.latest_version || "-"}</small>
              </button>
            ))
          ) : (
            <div className="runs-empty">{loading ? t("loading") : t("missingSkills")}</div>
          )}
        </div>

        <section className="catalog-detail workbench-detail">
          {selectedSkill ? (
            <>
              <div className="section-heading">
                <h3>{selectedSkill.title || selectedSkill.skill_slug}</h3>
                <span className="badge">{selectedSkill.source || t("localMode")}</span>
              </div>
              <dl className="run-kv compact">
                <dt>{t("skill")}</dt>
                <dd>{selectedSkill.skill_slug}</dd>
                <dt>{t("versionLabel")}</dt>
                <dd>{selectedVersion || "-"}</dd>
                <dt>{t("pathLabel")}</dt>
                <dd>{selectedSkill.relative_path || selectedSkill.latest_skill_path || "-"}</dd>
              </dl>

              <VersionTabs skill={selectedSkill} selectedVersion={selectedVersion} onSelect={setSelectedVersion} />

              <div className="skill-meta-grid">
                <MetadataPanel title={t("metadata")} metadata={recordValue(selectedSkill.metadata)} />
                <MetadataPanel title={t("versionMetadata")} metadata={recordValue(versionDetail?.metadata)} />
              </div>

              <section className="run-section nested-section">
                <div className="section-heading">
                  <h3>{t("skillMarkdown")}</h3>
                  <span className="badge">{selectedVersion || "-"}</span>
                </div>
                <pre className="markdown-panel">{versionDetail?.markdown || t("loading")}</pre>
              </section>

              {versionDetail?.diff ? (
                <section className="run-section nested-section">
                  <div className="section-heading">
                    <h3>{t("skillDiff")}</h3>
                    <span className="badge">{t("diff")}</span>
                  </div>
                  <pre className="diff-block">{versionDetail.diff}</pre>
                </section>
              ) : null}
            </>
          ) : (
            <p className="muted-text">{t("missingSkills")}</p>
          )}
        </section>
      </div>
    </section>
  );
}

function VersionTabs({
  skill,
  selectedVersion,
  onSelect
}: {
  skill: SkillSummary;
  selectedVersion: string;
  onSelect: (version: string) => void;
}) {
  const versions = skill.versions || [];
  if (!versions.length) {
    return null;
  }
  return (
    <div className="skill-version-tabs" role="tablist">
      {versions.map((version) => (
        <button
          className={version === selectedVersion ? "drill-tab active" : "drill-tab"}
          key={version}
          type="button"
          onClick={() => onSelect(version)}
        >
          {version}
        </button>
      ))}
    </div>
  );
}

function MetadataPanel({ title, metadata }: { title: string; metadata: JsonRecord | null }) {
  return (
    <section className="schema-panel">
      <h4>{title}</h4>
      <pre>{JSON.stringify(metadata || {}, null, 2)}</pre>
    </section>
  );
}

function recordValue(value: unknown): JsonRecord | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as JsonRecord;
}
