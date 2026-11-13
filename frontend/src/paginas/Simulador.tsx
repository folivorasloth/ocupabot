import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { avisarContadores, Cabecalho, Erro, Selo } from "../componentes/ui";

interface Fala { de: "voce" | "bot"; texto: string }
interface Estado { id: number; estado: string; fluxo: string | null; etapa: string | null }

const novoNumero = () => "5500000000" + String(Math.floor(Math.random() * 900) + 100);

export default function Simulador() {
  const [telefone, setTelefone] = useState(novoNumero);
  const [falas, setFalas] = useState<Fala[]>([]);
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [conversa, setConversa] = useState<Estado | null>(null);
  const [enviando, setEnviando] = useState(false);
  const fim = useRef<HTMLDivElement>(null);
  useEffect(() => { fim.current?.scrollIntoView({ block: "end" }); }, [falas.length]);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    const t = texto.trim();
    if (!t || enviando) return;
    setTexto("");
    setErro(null);
    setEnviando(true);
    setFalas((f) => [...f, { de: "voce", texto: t }]);
    try {
      const r = await api.post<{ respostas: string[]; conversa: Estado }>("/simulador/mensagem", { telefone, texto: t });
      setConversa(r.conversa);
      setFalas((f) => [...f, ...(r.respostas.length ? r.respostas : ["(sem resposta: a conversa está com a equipe)"]).map((x) => ({ de: "bot" as const, texto: x }))]);
      avisarContadores();
    } catch (err) { setErro((err as Error).message); } finally { setEnviando(false); }
  }

  async function devolver() {
    if (!conversa) return;
    setErro(null);
    try {
      await api.post(`/conversas/${conversa.id}/devolver`);
      setConversa({ ...conversa, estado: "BOT", fluxo: null, etapa: null });
      setFalas((f) => [...f, { de: "bot", texto: "(conversa devolvida ao bot: mande uma mensagem para continuar)" }]);
      avisarContadores();
    } catch (err) { setErro((err as Error).message); }
  }

  return (
    <>
      <Cabecalho titulo="Testar o bot" sub="Converse com o bot como se fosse pelo WhatsApp. Os pedidos aparecem de verdade em Pedidos do bot e Conversas.">
        <input className="campo w-44" value={telefone} onChange={(e) => setTelefone(e.target.value.replace(/\D/g, ""))} title="Número fictício" aria-label="Número fictício" />
        <button className="botao-secundario" onClick={() => { setFalas([]); setConversa(null); setTelefone(novoNumero()); }}>Novo contato</button>
      </Cabecalho>
      <Erro texto={erro} />
      <div className="cartao mx-auto max-w-xl p-0">
        {conversa && (
          <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-3 py-2 text-xs text-slate-600">
            <Selo valor={conversa.estado} />
            {conversa.estado === "BOT" ? <span>{conversa.etapa ? `o bot espera a resposta do passo ${conversa.etapa.toLowerCase().replace(/_/g, " ")}` : "no começo da conversa"}</span>
              : <><span>o bot não responde enquanto a conversa está com a equipe</span><button className="botao-secundario" onClick={devolver}>Devolver ao bot</button></>}
          </div>
        )}
        <div className="h-[60vh] space-y-2 overflow-y-auto bg-[#efeae2] p-3">
          {falas.length === 0 && <p className="py-6 text-center text-xs text-slate-500">Mande “oi” para começar. Experimente também “voltar”, “atendente” e “sair”.</p>}
          {falas.map((f, i) => (
            <div key={i} className={`flex ${f.de === "voce" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-sm shadow-sm ${f.de === "voce" ? "bg-[#d9fdd3]" : "bg-white"}`}>{f.texto}</div>
            </div>
          ))}
          <div ref={fim} />
        </div>
        <form onSubmit={enviar} className="flex gap-2 border-t border-slate-200 p-2">
          <input className="campo" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Digite uma mensagem (ex.: oi)" aria-label="Mensagem" autoFocus />
          <button className="botao-primario" disabled={enviando || !texto.trim()}>Enviar</button>
        </form>
      </div>
    </>
  );
}
