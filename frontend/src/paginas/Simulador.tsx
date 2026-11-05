import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Cabecalho, Erro } from "../componentes/ui";

interface Fala { de: "voce" | "bot"; texto: string }

export default function Simulador() {
  const [telefone, setTelefone] = useState("5500000000" + String(Math.floor(Math.random() * 900) + 100));
  const [falas, setFalas] = useState<Fala[]>([]);
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const fim = useRef<HTMLDivElement>(null);
  useEffect(() => { fim.current?.scrollIntoView({ block: "end" }); }, [falas.length]);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    const t = texto.trim();
    if (!t) return;
    setTexto("");
    setFalas((f) => [...f, { de: "voce", texto: t }]);
    try {
      const r = await api.post<{ respostas: string[] }>("/simulador/mensagem", { telefone, texto: t });
      setFalas((f) => [...f, ...(r.respostas.length ? r.respostas : ["(sem resposta: a conversa está com a equipe)"]).map((x) => ({ de: "bot" as const, texto: x }))]);
    } catch (err) { setErro((err as Error).message); }
  }

  return (
    <>
      <Cabecalho titulo="Simulador do bot" sub="Converse com o bot como se fosse pelo WhatsApp. Os pedidos aparecem de verdade em Aprovações e Conversas.">
        <input className="campo w-44" value={telefone} onChange={(e) => setTelefone(e.target.value.replace(/\D/g, ""))} title="Número fictício" />
        <button className="botao-secundario" onClick={() => { setFalas([]); setTelefone("5500000000" + String(Math.floor(Math.random() * 900) + 100)); }}>Novo contato</button>
      </Cabecalho>
      <Erro texto={erro} />
      <div className="cartao mx-auto max-w-xl p-0">
        <div className="h-[60vh] space-y-2 overflow-y-auto bg-[#efeae2] p-3">
          {falas.map((f, i) => (
            <div key={i} className={`flex ${f.de === "voce" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm shadow-sm ${f.de === "voce" ? "bg-[#d9fdd3]" : "bg-white"}`}>{f.texto}</div>
            </div>
          ))}
          <div ref={fim} />
        </div>
        <form onSubmit={enviar} className="flex gap-2 border-t border-slate-200 p-2">
          <input className="campo" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Digite uma mensagem (ex.: oi)" autoFocus />
          <button className="botao-primario">Enviar</button>
        </form>
      </div>
    </>
  );
}
