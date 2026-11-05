import { useEffect, useState } from "react";
import { api, qs } from "../api";
import { dataCurta, hojeIso } from "../formato";

interface Props { exames: number[]; data: string; horario: string; mudar: (data: string, horario: string) => void }

export default function EscolherHorario({ exames, data, horario, mudar }: Props) {
  const [livres, setLivres] = useState<string[] | null>(null);
  const [proximos, setProximos] = useState<{ data: string; horarios: string[] }[]>([]);

  useEffect(() => {
    if (!exames.length || !data) { setLivres(null); return; }
    api.get<{ horarios: string[] }>(`/vagas${qs({ data, exames })}`).then((r) => setLivres(r.horarios)).catch(() => setLivres([]));
  }, [exames.join(","), data]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!exames.length) { setProximos([]); return; }
    api.get<{ data: string; horarios: string[] }[]>(`/vagas/proximas${qs({ exames, dias: 6 })}`).then(setProximos).catch(() => setProximos([]));
  }, [exames.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-2">
      <div>
        <label className="rotulo">Data</label>
        <input type="date" className="campo" min={hojeIso()} value={data} onChange={(e) => mudar(e.target.value, "")} />
      </div>
      {proximos.length > 0 && (
        <div className="flex flex-wrap gap-1">
          <span className="text-xs text-slate-500">Próximos dias com vaga:</span>
          {proximos.map((p) => (
            <button type="button" key={p.data} className={`rounded border px-1.5 text-xs ${p.data === data ? "border-marca-500 bg-marca-50" : "border-slate-200"}`}
              onClick={() => mudar(p.data, "")}>{dataCurta(p.data)}</button>
          ))}
        </div>
      )}
      {!exames.length && <p className="text-xs text-slate-500">Escolha os exames para ver as vagas.</p>}
      {livres && (livres.length === 0 ? <p className="text-sm text-rose-600">Sem vaga nesse dia para esses exames.</p> : (
        <div className="flex max-h-40 flex-wrap gap-1 overflow-y-auto">
          {livres.map((h) => (
            <button type="button" key={h} onClick={() => mudar(data, h)}
              className={`rounded-md border px-2 py-1 text-xs ${h === horario ? "border-marca-600 bg-marca-600 text-white" : "border-slate-300 hover:border-marca-500"}`}>{h}</button>
          ))}
        </div>
      ))}
    </div>
  );
}
