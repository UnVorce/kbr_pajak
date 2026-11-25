# -*- coding: utf-8 -*-
"""Engine reasoning & SPARQL provenance mandiri (tanpa hardcode logika pajak di Python).

Mendukung dua layout direktori otomatis:
1. Workspace pengembangan (`fatih/`):
   - ontology/kbr_pajak_reasoning.owl
   - ontology/rule_map.json
   - data/export/kbr-data.ttl
2. Repo tim (`kbr_pajak/`):
   - ontology/kbr_pajak_reasoning.owl
   - ontology/rule_map.json
   - knowledge_json/rules/kbr-data.ttl
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from owlready2 import ThingClass, World, destroy_entity, sync_reasoner_hermit
from rdflib import Graph

BASE_IRI = "http://www.semanticweb.org/ontology/kbr_pajak#"


@dataclass(frozen=True)
class BackendPaths:
    root: Path
    reasoning_owl: Path
    rule_map_json: Path
    build_report_json: Path
    full_ttl: Path


def resolve_paths(base_dir: Optional[Path] = None) -> BackendPaths:
    """Temukan path artefak ontologi secara otomatis untuk fatih/ maupun kbr_pajak/."""
    env_root = os.environ.get("KBR_PROJECT_ROOT")
    root = Path(env_root).resolve() if env_root else (base_dir or Path(__file__).resolve().parents[1])

    reasoning_owl = Path(
        os.environ.get("KBR_REASONING_OWL") or (root / "ontology" / "kbr_pajak_reasoning.owl")
    )
    rule_map_json = Path(
        os.environ.get("KBR_RULE_MAP_JSON") or (root / "ontology" / "rule_map.json")
    )
    build_report_json = root / "ontology" / "ontology_build_report.json"

    env_ttl = os.environ.get("KBR_FULL_TTL")
    if env_ttl:
        full_ttl = Path(env_ttl)
    elif (root / "data" / "export" / "kbr-data.ttl").exists():
        full_ttl = root / "data" / "export" / "kbr-data.ttl"
    else:
        full_ttl = root / "knowledge_json" / "rules" / "kbr-data.ttl"

    return BackendPaths(
        root=root,
        reasoning_owl=reasoning_owl,
        rule_map_json=rule_map_json,
        build_report_json=build_report_json,
        full_ttl=full_ttl,
    )


class KBRReasoningEngine:
    """Menjalankan HermiT pada World() terisolasi per-request dan query SPARQL ter-cache."""

    def __init__(self, paths: Optional[BackendPaths] = None) -> None:
        self.paths = paths or resolve_paths()
        self._rdf_graph: Optional[Graph] = None
        self._rdf_lock = threading.Lock()
        self._reasoner_lock = threading.Lock()

    def get_graph(self) -> Graph:
        with self._rdf_lock:
            if self._rdf_graph is None:
                if not self.paths.full_ttl.exists():
                    raise FileNotFoundError(f"File RDF tidak ditemukan: {self.paths.full_ttl}")
                g = Graph()
                g.parse(str(self.paths.full_ttl), format="turtle")
                self._rdf_graph = g
            return self._rdf_graph

    def health(self) -> dict:
        report = {}
        if self.paths.build_report_json.exists():
            report = json.loads(self.paths.build_report_json.read_text(encoding="utf-8"))
        return {
            "status": "ok" if self.paths.reasoning_owl.exists() else "degraded",
            "reasoning_owl_exists": self.paths.reasoning_owl.exists(),
            "full_ttl_exists": self.paths.full_ttl.exists(),
            "rdf_loaded_in_memory": self._rdf_graph is not None,
            "rdf_triples": len(self._rdf_graph) if self._rdf_graph is not None else None,
            "reasoning_classes": report.get("reasoning_classes"),
            "reasoning_individuals": report.get("reasoning_individuals"),
            "swrl_rules": report.get("swrl_rules"),
            "full_rules_exported": report.get("full_rules_exported"),
        }

    def get_catalog(self) -> Dict[str, Any]:
        if not self.paths.rule_map_json.exists():
            raise FileNotFoundError(f"rule_map.json tidak ditemukan: {self.paths.rule_map_json}")
        return json.loads(self.paths.rule_map_json.read_text(encoding="utf-8"))

    def get_preset_scenarios(self) -> Dict[str, Any]:
        if not self.paths.build_report_json.exists():
            return {}
        data = json.loads(self.paths.build_report_json.read_text(encoding="utf-8"))
        return data.get("inferred_scenarios", {})

    def get_options(self) -> Dict[str, Any]:
        """Ambil daftar pilihan JenisPekerjaan & WilayahDaerah langsung dari ontologi OWL."""
        if not self.paths.reasoning_owl.exists():
            raise FileNotFoundError(f"File ontologi tidak ditemukan: {self.paths.reasoning_owl}")
        w = World()
        onto = w.get_ontology(str(self.paths.reasoning_owl)).load()
        jobs = []
        for j in sorted(onto.JenisPekerjaan.instances(), key=lambda x: x.name):
            cats = sorted(c.name for c in j.is_a if isinstance(c, ThingClass) and c.name != "JenisPekerjaan")
            jobs.append({
                "id": j.name,
                "label": j.label[0] if j.label else j.name,
                "kategori": cats[0] if cats else "JenisPekerjaan",
            })
        regions = [
            {"id": r.name, "label": r.label[0] if r.label else r.name}
            for r in sorted(onto.WilayahDaerah.instances(), key=lambda x: x.name)
        ]
        return {"jobs": jobs, "regions": regions}

    def reason(self, wp_id: str, wp_kind: str, props: Dict[str, Any]) -> dict:
        """Evaluasi 1 individu WajibPajak dengan HermiT di World() terisolasi."""
        if not self.paths.reasoning_owl.exists():
            raise FileNotFoundError(f"File ontologi tidak ditemukan: {self.paths.reasoning_owl}")

        t0 = time.perf_counter()
        with self._reasoner_lock:
            w = World()
            onto = w.get_ontology(str(self.paths.reasoning_owl)).load()
            with onto:
                # Bersihkan individu skenario demo & aturan tambahan non-katalog agar inferensi tunggal steril & cepat
                for ind in list(onto.WajibPajak.instances()):
                    destroy_entity(ind)
                linked_aturan = set()
                for cat_cls in (onto.TarifPajak, onto.FasilitasPerpajakan, onto.KewajibanPajak, onto.SanksiAdministratif):
                    for it in cat_cls.instances():
                        for at in getattr(it, "didasarkanPadaAturan", []):
                            linked_aturan.add(at.name)
                for ind in list(onto.AturanHukum.instances()):
                    if ind.name not in linked_aturan:
                        destroy_entity(ind)

                cls = getattr(onto, wp_kind, None)
                if cls is None:
                    cls = onto.Badan if wp_kind == "Badan" else onto.OrangPribadi
                wp = cls(wp_id)
                applied_props: Dict[str, Any] = {}
                for k, v in props.items():
                    if v is None:
                        continue
                    if k in ("memilikiPekerjaan", "berdomisiliDi"):
                        vals = v if isinstance(v, (list, tuple)) else [v]
                        objs = [getattr(onto, str(item), None) for item in vals]
                        resolved = [o for o in objs if o is not None]
                        setattr(wp, k, resolved)
                        applied_props[k] = [o.name for o in resolved]
                    elif hasattr(wp, k):
                        setattr(wp, k, v)
                        applied_props[k] = v
                sync_reasoner_hermit(w, infer_property_values=True, debug=0)

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        def _explain(items) -> List[dict]:
            out = []
            seen = set()
            for it in items:
                if it.name in seen:
                    continue
                seen.add(it.name)
                just = []
                for at in getattr(it, "didasarkanPadaAturan", []):
                    just.append({
                        "rule_id": getattr(at, "hasRuleId", None),
                        "source_locator": getattr(at, "hasSourceLocator", None),
                        "source_quote": getattr(at, "hasSourceQuote", None),
                        "validation_status": getattr(at, "hasStatusValidasi", None),
                        "regulasi": [r.hasDocumentId for r in getattr(at, "diaturDalam", [])],
                        "mk_refs": [m.hasDocumentId for m in getattr(at, "terdampakPutusanMK", [])],
                        "sema_refs": [s.hasDocumentId for s in getattr(at, "merujukSEMA", [])],
                    })
                out.append({
                    "id": it.name,
                    "label": it.label[0] if it.label else it.name,
                    "tarif_persen": getattr(it, "hasTarifPersen", None),
                    "justifikasi": just,
                })
            return sorted(out, key=lambda x: x["id"])

        direct_classes = sorted(
            c.name for c in wp.is_a
            if isinstance(c, ThingClass) and c.name != "Thing"
        )
        inferred_classes = sorted(
            c.name for c in wp.INDIRECT_is_a
            if isinstance(c, ThingClass) and c.name != "Thing"
        )

        estimasi_pajak = self._estimate_nominal_sparql(w, wp_id)

        return {
            "wp_id": wp_id,
            "wp_kind": wp_kind,
            "applied_properties": applied_props,
            "direct_classes": direct_classes,
            "inferred_classes": inferred_classes,
            "tarif": _explain(wp.dikenaiTarif),
            "fasilitas": _explain(wp.memilikiFasilitas),
            "kewajiban": _explain(wp.memilikiKewajiban),
            "sanksi": _explain(wp.berisikoSanksi),
            "estimasi_pajak": estimasi_pajak,
            "reasoner": "HermiT (OWL 2 SROIQ(D) + SWRL DL-safe) + SPARQL BIND",
            "elapsed_ms": elapsed_ms,
        }

    def _estimate_nominal_sparql(self, world: World, wp_id: str) -> Dict[str, Any]:
        """Hitung estimasi nominal pajak secara deklaratif via SPARQL BIND di atas graf hasil HermiT."""
        g = world.as_rdflib_graph()
        wp_ref = f"kbr:{wp_id}"
        out: Dict[str, Any] = {
            "metode": "SPARQL 1.1 BIND atas graf RDF hasil inferensi HermiT (indikatif)",
            "rincian": {},
        }

        # 1. PPh Badan (Pasal 31E / Tbk 19% / Umum 22% / UMKM Badan 0,5% / BUT Branch Profit 20%)
        q_badan = f"""
        PREFIX kbr: <{BASE_IRI}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        SELECT ?pphBadan ?penghematan31E ?pphUmkmBadan ?butBpt
        WHERE {{
          BIND({wp_ref} AS ?wp)
          BIND(EXISTS {{ ?wp rdf:type/rdfs:subClassOf* kbr:Badan }} AS ?isBadan)
          BIND(EXISTS {{ ?wp rdf:type/rdfs:subClassOf* kbr:BadanUMKM }} AS ?isUmkmBadan)
          OPTIONAL {{ ?wp kbr:hasOmzetTahunan ?omzet . }}
          OPTIONAL {{ ?wp kbr:hasPenghasilanKenaPajakTahunan ?pkp . }}
          OPTIONAL {{ ?wp kbr:memilikiFasilitas ?f31e . FILTER(?f31e = kbr:Fasilitas_Pasal31E_Diskon50Pct_11Pct) }}
          OPTIONAL {{ ?wp kbr:dikenaiTarif kbr:Tarif_PPhBadan_Tbk_19Pct . kbr:Tarif_PPhBadan_Tbk_19Pct kbr:hasTarifPersen ?t19 . }}
          OPTIONAL {{ ?wp kbr:dikenaiTarif kbr:Tarif_PPhBadan_22Pct . kbr:Tarif_PPhBadan_22Pct kbr:hasTarifPersen ?t22 . }}
          OPTIONAL {{ ?wp kbr:dikenaiTarif kbr:Tarif_PPh26_4_BUT_BranchProfit_20Pct . kbr:Tarif_PPh26_4_BUT_BranchProfit_20Pct kbr:hasTarifPersen ?tBut . }}
          BIND(IF(?isUmkmBadan && BOUND(?omzet), xsd:decimal(?omzet) * 0.005, ?unbound) AS ?pphUmkmBadan)
          BIND(IF(BOUND(?f31e) && BOUND(?pkp) && BOUND(?omzet) && xsd:decimal(?omzet) > 0,
                  IF(xsd:decimal(?omzet) > 4800000000.0, 4800000000.0 / xsd:decimal(?omzet), 1.0),
                  0.0) AS ?ratio31E)
          BIND(IF(?isBadan && BOUND(?pkp),
                  IF(BOUND(?f31e) && BOUND(?omzet) && xsd:decimal(?omzet) > 0,
                     (xsd:decimal(?pkp) * ?ratio31E * 0.11) + (xsd:decimal(?pkp) * (1.0 - ?ratio31E) * 0.22),
                     IF(BOUND(?t19),
                        xsd:decimal(?pkp) * (xsd:decimal(?t19) / 100.0),
                        IF(BOUND(?t22), xsd:decimal(?pkp) * (xsd:decimal(?t22) / 100.0), ?unbound))),
                  ?unbound) AS ?pphBadan)
          BIND(IF(BOUND(?f31e) && BOUND(?pkp) && BOUND(?omzet) && xsd:decimal(?omzet) > 0,
                  xsd:decimal(?pkp) * ?ratio31E * 0.11,
                  ?unbound) AS ?penghematan31E)
          BIND(IF(BOUND(?tBut) && BOUND(?pphBadan),
                  (xsd:decimal(?pkp) - ?pphBadan) * (xsd:decimal(?tBut) / 100.0),
                  ?unbound) AS ?butBpt)
        }}
        LIMIT 1
        """
        for row in g.query(q_badan):
            if row.pphUmkmBadan is not None:
                out["rincian"]["pph_final_umkm_badan_idr"] = round(float(row.pphUmkmBadan), 2)
            if row.pphBadan is not None:
                out["rincian"]["pph_badan_idr"] = round(float(row.pphBadan), 2)
            if row.penghematan31E is not None:
                out["rincian"]["penghematan_pasal_31e_idr"] = round(float(row.penghematan31E), 2)
            if row.butBpt is not None:
                out["rincian"]["branch_profit_tax_but_idr"] = round(float(row.butBpt), 2)

        # 2. PPh Orang Pribadi (UMKM OP bebas 500jt + Pasal 17 5 Lapis Progresif atas PKP)
        q_op = f"""
        PREFIX kbr: <{BASE_IRI}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        SELECT ?pphUmkmOp ?porsiBebas500Jt ?pphOp17
        WHERE {{
          BIND({wp_ref} AS ?wp)
          BIND(EXISTS {{ ?wp rdf:type/rdfs:subClassOf* kbr:OrangPribadi }} AS ?isOp)
          OPTIONAL {{ ?wp kbr:hasOmzetTahunan ?omzet . }}
          OPTIONAL {{ ?wp kbr:hasPenghasilanKenaPajakTahunan ?pkp . }}
          OPTIONAL {{ ?wp kbr:memilikiFasilitas ?fBebas . FILTER(?fBebas = kbr:Fasilitas_OP_UMKM_BebasPPh_500Jt) }}
          OPTIONAL {{ ?wp kbr:memilikiFasilitas ?fPp55 . FILTER(?fPp55 = kbr:Fasilitas_PP55_Final_0_5Pct) }}
          BIND(IF(?isOp && BOUND(?fBebas) && BOUND(?omzet),
                  IF(xsd:decimal(?omzet) <= 500000000.0, xsd:decimal(?omzet), 500000000.0),
                  ?unbound) AS ?porsiBebas500Jt)
          BIND(IF(?isOp && BOUND(?fBebas) && BOUND(?omzet),
                  IF(BOUND(?fPp55) && xsd:decimal(?omzet) > 500000000.0,
                     (xsd:decimal(?omzet) - 500000000.0) * 0.005,
                     0.0),
                  ?unbound) AS ?pphUmkmOp)
          BIND(IF(?isOp && BOUND(?pkp) && xsd:decimal(?pkp) > 0, xsd:decimal(?pkp), 0.0) AS ?p)
          BIND(IF(?p < 60000000.0, ?p, 60000000.0) * 0.05 AS ?l1)
          BIND(IF(?p > 60000000.0, (IF(?p < 250000000.0, ?p, 250000000.0) - 60000000.0) * 0.15, 0.0) AS ?l2)
          BIND(IF(?p > 250000000.0, (IF(?p < 500000000.0, ?p, 500000000.0) - 250000000.0) * 0.25, 0.0) AS ?l3)
          BIND(IF(?p > 500000000.0, (IF(?p < 5000000000.0, ?p, 5000000000.0) - 500000000.0) * 0.30, 0.0) AS ?l4)
          BIND(IF(?p > 5000000000.0, (?p - 5000000000.0) * 0.35, 0.0) AS ?l5)
          BIND(IF(?isOp && BOUND(?pkp), ?l1 + ?l2 + ?l3 + ?l4 + ?l5, ?unbound) AS ?pphOp17)
        }}
        LIMIT 1
        """
        for row in g.query(q_op):
            if row.porsiBebas500Jt is not None:
                out["rincian"]["porsi_omzet_bebas_500jt_idr"] = round(float(row.porsiBebas500Jt), 2)
            if row.pphUmkmOp is not None:
                out["rincian"]["pph_final_umkm_op_idr"] = round(float(row.pphUmkmOp), 2)
            if row.pphOp17 is not None:
                out["rincian"]["pph_op_pasal17_idr"] = round(float(row.pphOp17), 2)

        # 3. PPN (12% BKP Mewah vs 11% Efektif Non-Mewah DPP 11/12) & PBB-P2
        q_ppn_pbb = f"""
        PREFIX kbr: <{BASE_IRI}>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        SELECT ?ppnTerutang ?pbbTerutang
        WHERE {{
          BIND({wp_ref} AS ?wp)
          OPTIONAL {{ ?wp kbr:hasDPP_PPN ?dpp . }}
          OPTIONAL {{ ?wp kbr:dikenaiTarif ?t12 . FILTER(?t12 = kbr:Tarif_PPN_12Pct) }}
          OPTIONAL {{ ?wp kbr:dikenaiTarif ?t11 . FILTER(?t11 = kbr:Tarif_PPN_Efektif_11Pct) }}
          OPTIONAL {{ ?wp kbr:hasNilaiNJOP ?njop . }}
          OPTIONAL {{ ?wp kbr:hasNJOPTKP_PBB ?njoptkpIn . }}
          OPTIONAL {{ ?wp kbr:hasPersentaseNJOP_PBB ?njopPctIn . }}
          OPTIONAL {{ ?wp kbr:berdomisiliDi ?wil . }}
          OPTIONAL {{ ?wp kbr:isDomisiliDKI ?isDki . }}
          OPTIONAL {{
            ?wp kbr:dikenaiTarif ?tpbb .
            FILTER(?tpbb IN (
              kbr:Tarif_PBB_DKI_0_5Pct, kbr:Tarif_PBB_Semarang_0_3Pct,
              kbr:Tarif_PBB_Surabaya_L1_0_05Pct, kbr:Tarif_PBB_Surabaya_L2_0_10Pct,
              kbr:Tarif_PBB_Surabaya_L3_0_15Pct, kbr:Tarif_PBB_Surabaya_L4_0_20Pct,
              kbr:Tarif_PBB_Surabaya_L5_0_25Pct, kbr:Tarif_PBB_Surabaya_L6_0_30Pct
            ))
            ?tpbb kbr:hasTarifPersen ?ratePbb .
          }}
          BIND(IF(BOUND(?dpp) && BOUND(?t12), xsd:decimal(?dpp) * 0.12,
                  IF(BOUND(?dpp) && BOUND(?t11), xsd:decimal(?dpp) * (11.0 / 12.0) * 0.12, ?unbound)) AS ?ppnTerutang)
          BIND(IF(BOUND(?njoptkpIn), xsd:decimal(?njoptkpIn),
                  IF((BOUND(?wil) && ?wil = kbr:Wilayah_DKI_Jakarta) || (BOUND(?isDki) && ?isDki = true), 60000000.0,
                     IF(BOUND(?wil) && ?wil = kbr:Wilayah_Kota_Surabaya, 15000000.0, 10000000.0))) AS ?njoptkp)
          BIND(IF(BOUND(?njopPctIn), xsd:decimal(?njopPctIn) / 100.0, 1.0) AS ?njopRatio)
          BIND(IF(BOUND(?ratePbb) && BOUND(?njop),
                  IF(xsd:decimal(?njop) > ?njoptkp, (xsd:decimal(?njop) - ?njoptkp) * ?njopRatio * (xsd:decimal(?ratePbb) / 100.0), 0.0),
                  ?unbound) AS ?pbbTerutang)
        }}
        LIMIT 1
        """
        for row in g.query(q_ppn_pbb):
            if row.ppnTerutang is not None:
                out["rincian"]["ppn_terutang_idr"] = round(float(row.ppnTerutang), 2)
            if row.pbbTerutang is not None:
                out["rincian"]["pbb_terutang_idr"] = round(float(row.pbbTerutang), 2)

        # 4. Sanksi Denda KUP Nominal Tetap (OP 100rb, Badan 1jt, Masa PPN 500rb)
        q_denda = f"""
        PREFIX kbr: <{BASE_IRI}>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        SELECT (SUM(xsd:decimal(?nom)) AS ?totalDenda)
        WHERE {{
          {wp_ref} kbr:berisikoSanksi ?s .
          ?s kbr:hasNominalSanksi ?nom .
        }}
        """
        for row in g.query(q_denda):
            if row.totalDenda is not None and float(row.totalDenda) > 0:
                out["rincian"]["denda_administratif_tetap_idr"] = round(float(row.totalDenda), 2)

        return out

    def query_provenance(
        self,
        *,
        rule_id: Optional[str] = None,
        document_id: Optional[str] = None,
        domain: Optional[str] = None,
        rule_type: Optional[str] = None,
        quote_contains: Optional[str] = None,
        limit: int = 20,
    ) -> List[dict]:
        """Query SPARQL lokal pada kbr-data.ttl (12.907 aturan)."""
        g = self.get_graph()
        filters = []
        if rule_id:
            safe = rule_id.replace("\\", "\\\\").replace('"', '\\"')
            filters.append(f'FILTER(STR(?ruleId) = "{safe}")')
        if document_id:
            safe = document_id.replace("\\", "\\\\").replace('"', '\\"')
            filters.append(f'FILTER(STR(?docId) = "{safe}")')
        if domain:
            safe = domain.replace("\\", "\\\\").replace('"', '\\"')
            filters.append(f'FILTER(CONTAINS(STR(?domainUri), "{safe}"))')
        if rule_type:
            safe = rule_type.replace("\\", "\\\\").replace('"', '\\"')
            filters.append(f'FILTER(STR(?rtypeUri) = "{BASE_IRI}{safe}")')
        if quote_contains:
            safe = quote_contains.replace("\\", "\\\\").replace('"', '\\"')
            filters.append(f'FILTER(CONTAINS(LCASE(STR(?quote)), LCASE("{safe}")))')

        filter_clause = "\n            ".join(filters)
        safe_limit = max(1, min(int(limit), 200))
        q = f"""
        PREFIX kbr: <{BASE_IRI}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?aturan ?ruleId ?rtypeUri ?docId ?locator ?quote ?status ?domainUri ?mk ?sema
        WHERE {{
            ?aturan rdf:type ?rtypeUri ;
                    kbr:hasRuleId ?ruleId ;
                    kbr:hasSourceLocator ?locator ;
                    kbr:diaturDalam ?reg .
            ?reg kbr:hasDocumentId ?docId .
            OPTIONAL {{ ?aturan kbr:hasSourceQuote ?quote . }}
            OPTIONAL {{ ?aturan kbr:hasStatusValidasi ?status . }}
            OPTIONAL {{ ?aturan kbr:termasukDomain ?domainUri . }}
            OPTIONAL {{ ?aturan kbr:terdampakPutusanMK ?mk . }}
            OPTIONAL {{ ?aturan kbr:merujukSEMA ?sema . }}
            {filter_clause}
        }}
        ORDER BY ?docId ?locator ?ruleId
        LIMIT {safe_limit}
        """
        rows = []
        for r in g.query(q):
            rows.append({
                "aturan_uri": str(r.aturan),
                "rule_id": str(r.ruleId),
                "rule_class": str(r.rtypeUri).split("#")[-1],
                "document_id": str(r.docId),
                "source_locator": str(r.locator),
                "source_quote": str(r.quote) if r.quote is not None else "",
                "validation_status": str(r.status) if r.status is not None else "",
                "domain": str(r.domainUri).split("#")[-1] if r.domainUri is not None else None,
                "mk_ref": str(r.mk).split("#")[-1] if r.mk is not None else None,
                "sema_ref": str(r.sema).split("#")[-1] if r.sema is not None else None,
            })
        return rows

    def sparql_stats(self) -> dict:
        """Ringkasan jumlah aturan per domain & kelas dari graph RDF."""
        g = self.get_graph()
        q_dom = f"""
        PREFIX kbr: <{BASE_IRI}>
        SELECT ?domainUri (COUNT(?a) AS ?cnt)
        WHERE {{
            ?a kbr:hasRuleId ?rid ;
               kbr:termasukDomain ?domainUri .
        }}
        GROUP BY ?domainUri
        ORDER BY DESC(?cnt)
        """
        q_cls = f"""
        PREFIX kbr: <{BASE_IRI}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?rtypeUri (COUNT(?a) AS ?cnt)
        WHERE {{
            ?a kbr:hasRuleId ?rid ;
               rdf:type ?rtypeUri .
        }}
        GROUP BY ?rtypeUri
        ORDER BY DESC(?cnt)
        """
        by_domain = {str(r.domainUri).split("#")[-1]: int(r.cnt) for r in g.query(q_dom)}
        by_class = {str(r.rtypeUri).split("#")[-1]: int(r.cnt) for r in g.query(q_cls)}
        return {
            "total_triples": len(g),
            "total_rules": sum(by_class.values()),
            "by_domain": by_domain,
            "by_class": by_class,
        }
