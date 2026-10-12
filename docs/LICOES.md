# Lições de MCPs em produção com usuários não técnicos

O Luis tem três servidores MCP em produção, usados por pessoas não técnicas em português e inglês: um grupo de
restaurantes nos EUA, uma rede de lojas de varejo no Brasil e uma empresa de paisagismo no Brasil. Este
documento traz o que esse uso real ensinou e como cada lição entra na demo.

**Anonimizado de propósito:** sem nomes, números de negócio nem caminhos dos repositórios privados, onde estão as
fontes detalhadas, com arquivo e commit. Levantamento de 07/10/2026.

## 1. O que aconteceu de fato

**Adoção**
- **Entregar foi mais difícil que construir.** Um servidor ficou pronto e endurecido por 8 semanas com uso zero,
  porque o acesso nunca chegou aos usuários. Em outro sistema, o que aumentou o uso não foi o MCP, foi um aviso
  diário ("esperando você") no e-mail e no menu.
- **OAuth foi o que destravou o uso.** Chave pessoal servia ao Claude Desktop; o OAuth 2.1 (registro dinâmico,
  PKCE, refresh rotativo) abriu o claude.ai web e o celular. Entrar com o login do próprio sistema, sem chave
  para guardar, e revogar desativando o usuário.
- **Cada usuário escolheu um cliente diferente.** Uma usou só o Claude; outro adotou pelo ChatGPT e fez 14
  consultas na primeira noite.
- **O cliente guarda descrições de tools antigas.** Depois de um deploy que muda descrição, o claude.ai continuou
  respondendo com a versão anterior até o conector ser desligado e religado; cinco respostas de um eval
  contradisseram a tool por isso. O ChatGPT nem pede a lista de tools de novo: é preciso recriar o conector.
- **Um usuário usa o ChatGPT como redator:** os textos que ele manda ao sistema vêm redigidos pela IA, longos e
  estruturados (um pedido com 22 itens chegou cortado em 5 mil caracteres sem aviso).

**Como perguntam**
- **Na primeira sessão real de um sócio, nenhuma tool curada foi usada:** 21 de 23 chamadas foram SQL livre. As
  tools tinham sido feitas para a pergunta operacional do dia (uma loja, janela móvel); o sócio fazia análise
  estratégica (todas as lojas, período escolhido por ele, comparação, Pareto). 14 de 21 perguntas eram lacuna.
- **Um quarto da sessão foi auditoria de confiança** ("dá para confiar nesse custo?"), não pedido de número.
- **Redesenhando as tools pelo log de uso**, num segundo sistema o SQL livre caiu para 11% das chamadas.
- Perguntas reais têm cara de reunião: "como está a semana e quanto falta por dia útil para a meta?", "o que vence
  nos próximos 60 dias?", "por que o caixa e o resultado andaram diferentes?", "essa venda está errada".

**Confiança**
- **"Número errado com cara de certo" foi o problema nº 1:** filtro que não casa e volta 0, média de médias,
  período com fim exclusivo que some com o último dia, semana parcial lida como queda.
- **O log de chamadas resolve disputa de número nos dois sentidos.** Um "crescimento de 8%" citado por uma
  usuária parecia errado; o log mostrou a consulta exata que ela tinha feito, e o número estava **certo** (quem
  leu errado foi o analista).
- **Um erro real veio de busca por texto:** uma consulta do modelo filtrou "tênis" por substring e pegou também
  "sapatênis", distorcendo a comparação entre lojas em cerca de 11 pontos. A correção foi mandar o modelo usar a
  análise pronta antes de escrever consulta própria, e criar um de-para de classes. É exatamente o tipo de
  ambiguidade de vocabulário que sinônimos e categorias resolvem numa busca bem configurada.
- **Somar unidades diferentes:** calçados em pares e acessórios em peças apareceram somados num ranking de mais
  vendidos (meias no topo). Virou regra: nunca somar os dois.
- Um acesso revogado quebrou um relatório por 33 dias sem ninguém ver, e o modelo "consertou" usando uma fonte
  pior. Não havia canal de "isso está errado". Lição: monitorar a superfície que o usuário usa (um teste periódico
  das tools), porque o fallback degrada sem dar erro. E rotular a fonte não basta quando quem lê é um LLM: precisa
  de aviso explícito.

**Escrita**
- **Mesma tool, dois clientes, comportamentos diferentes:** o Claude parou para confirmar por prudência própria;
  o ChatGPT gravou sem pedir o sim, porque a descrição da tool não exigia. Correção: a escrita só acontece com
  `confirmado=true`; sem ele volta o rascunho. "Pedido ou queixa não é autorização."
- **Limite conhecido:** `confirmado=true` não impede o modelo de pular a etapa ou trocar o valor depois de
  mostrar. Nesta demo: uma confirmação com código ligado ao texto exato que foi mostrado (item 4 abaixo).

**Contexto e instruções**
- **Instruções longas chegam cortadas no cliente** (cerca de 2 mil de 21 mil caracteres). Regra crítica vai na
  descrição da tool; instruções do servidor com menos de 2 mil caracteres.
- Vocabulário do usuário, em português (no varejo de moda: referência, grade, pares × peças).
- Descobrir schema custava cerca de 20% das chamadas até existir um dicionário consultável.

**Avaliação e operação**
- Golden set de **perguntas reais com a resposta conferida na tela**, rodado antes de entregar o conector e a
  cada tool nova; rodado também no ChatGPT.
- **O log de auditoria é o roadmap:** o campo de propósito das consultas livres escreveu sozinho a fila de tools.
- MCP num segundo app com deploy manual ficou 8 semanas atrás do banco. Depois: MCP dentro do app, deploy único,
  tempo máximo por tool.
- **Armadilhas de eval que já custaram caro:** perguntas em inglês e de uma rodada só, quando os usuários
  perguntam em português e com follow-up; resposta esperada que vem da mesma fonte que se quer testar (circular);
  um verificador que não distingue recusa de afirmação ("eval com verde falso é pior que nenhum"); teste que não
  passa pelo protocolo real e deixa quebrar a assinatura da tool; o mesmo modelo extraindo e julgando.
- **Tamanho de resposta importa:** uma tarefa agendada que perguntava "tem novidade?" de hora em hora recebia
  cerca de 14 KB por chamada, quase sempre sem novidade. Virou uma resposta enxuta com `ha_novidade`.
- **Busca de documentos por substring trouxe ruído e não respeitava a permissão de cada usuário.** Virou busca
  ranqueada (BM25) com filtro por permissão.

## 2. Como cada lição entra na demo

Status em 12/10/2026 entre colchetes: [feito], [parcial] ou [não feito], com o porquê.

1. **Tools para a pergunta estratégica:** período livre, todas as categorias, comparação lado a lado.
   Ex.: `buscas_sem_resultado(inicio, fim)`, `demanda_por_tamanho(inicio, fim, categoria)`,
   `sugestao_de_reposicao(categoria)`. [feito; comparação lado a lado só entre as lojas pt e en]
2. **Bloco `dados` em toda resposta:** período efetivo, frescor e retenção (o analytics do Free guarda 7 dias,
   então "não houve" e "fora da janela" são coisas diferentes). "Busca sem resultado não é demanda zero."
   [feito: `sobre_os_dados`, com a parte sintética do período]
3. **Nome que não casa falha listando os valores válidos** (categoria, tamanho, índice); nunca 0 em silêncio.
   O Productivity MCP oficial da Algolia faz o contrário (observado em 07/10/2026): índice inexistente volta
   `null`/0 sem erro. É um contraste concreto para mostrar na demo. [feito]
4. **Escrita (sinônimo, regra) só com `confirmado=true`**, devolvendo rascunho e diff; a regra na descrição da
   tool; log com como desfazer. Testar no Claude **e** no ChatGPT. Um passo além do que já está em produção:
   a confirmação carrega o **hash do diff mostrado**, e o servidor recusa se o que vai gravar não for exatamente
   aquilo. [feito no sinônimo, só no modo local; regra (Rule) não tem tool]
5. **Sinônimos de verdade, não substring:** a demo mostra "tênis" × "sapatênis" como caso de configuração (o
   erro de 11 pontos acima é o argumento de negócio para sinônimos e categorias bem feitos). [feito]
6. **Instruções curtas** (< 2 mil caracteres), em pt-BR, com o vocabulário do merchandiser (grade, ruptura,
   "tênis" × "sneaker"). [feito]
7. **Tool de cobertura e confiança:** até quando vai o analytics, que parte do catálogo tem estoque por tamanho,
   quantos SKUs sem eventos. [feito, sem a contagem de eventos]
8. **Canal "isso está errado":** `reportar_problema` capturando a última chamada automaticamente. [feito]
9. **Tool genérica de analytics com `para_que` obrigatório**, cujo log vira a lista das próximas tools (o
   análogo do SQL livre, que não existe na Algolia). [não feito: o Productivity MCP oficial já faz a leitura crua
   de analytics; o copiloto se diferencia pela decisão]
10. **Golden set em camadas, em português e com follow-up, nunca circular:** smoke, invariantes (soma por tamanho = total), relevância das consultas pt-BR, e
   escrita que tem de parar na confirmação. Conferido no dashboard da Algolia (hipótese a validar: a Analytics API
   do Free devolve os mesmos agregados do dashboard). [parcial: golden set de busca em pt e en; o copiloto foi
   avaliado em quatro rodadas no Claude e no ChatGPT, ainda sem eval automático]
11. **README avisa:** depois de mudar tools, reconectar o conector. [feito]
12. **Assistente de compra:** nunca afirmar estoque ou tamanho sem dado da tool; sem o tamanho, dizer e oferecer
    alternativa (e registrar como demanda perdida); entre produtos parecidos, perguntar em vez de escolher.
    [feito: o aviso de "quando chegar" vira demanda perdida na sugestão de reposição]
13. **MCP e loja no mesmo deploy**, com tempo máximo por tool (o Agent Studio corta MCP em 10 s). [parcial: tempo
    máximo por tool sim; a loja fica na Vercel e o MCP no Fly, escolha de hospedagem sem teste do MCP na Vercel]
14. **Respostas enxutas** (o cliente paga em tokens e em atenção), com resumo antes do detalhe. [feito]
15. **Plano de entrega na demo:** o README tem o passo a passo para conectar o MCP no Claude e no ChatGPT em
    linguagem de usuário, porque a lição nº 1 foi que acesso que não chega ao usuário vale zero. [feito]

## 3. Em uma frase

"With real non-technical users, the curated tools were ignored until I redesigned them from the usage log; the
same write tool asked for confirmation in one client and not in the other; and the biggest risk was never an
error, it was a wrong number that looked right. This demo carries those three fixes."
