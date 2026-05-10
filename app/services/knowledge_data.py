"""
Knowledge base seed data — church content for the RAG layer.

Imported by `scripts/seed_knowledge.py` (manual full re-seed) and by
`rag_service.seed_if_empty()` (idempotent boot-time seed).
"""

# Each entry: (category, title, content)
KNOWLEDGE_ENTRIES: list[tuple[str, str, str]] = [
    # ── Informações gerais ──
    (
        "geral",
        "Informações de contato e localização da igreja",
        "A Igreja Batista Lírio dos Vales de Jardim Armação fica na R. Pedro Silva Ribeiro, 272 – Armação, CEP 41750-130, Salvador/BA. "
        "WhatsApp: 71 0 8293 8239. Instagram: @lirioarmacao. "
        "O lema da igreja é: Enraizar. Crescer. Frutificar. "
        "Propósito: Unidos para conhecê-Lo e fazê-Lo conhecido."
    ),
    (
        "estrutura",
        "Equipe pastoral e ministérios",
        "Pastor Presidente: Pr. Diogo Dantas. "
        "Pr. Diogo cuida de: Adolescentes, Artes, Intercessão, Mídias Sociais e Missões. "
        "Pra. Tainan cuida de: Acolhimento, Crianças/Juniores, Diaconato e Mulheres. "
        "Pr. Paulo cuida de: GC's (Grupos de Comunhão), Família e Beneficência. "
        "Pr. Saulo cuida de: Música. "
        "Pr. Silas cuida de: Jovens. "
        "O Staff Administrativo cuida de: Secretaria, Tesouraria, Manutenção e Contabilidade."
    ),
    (
        "estrutura",
        "Estrutura e funcionamento da igreja",
        "A igreja funciona em um espaço físico comunitário (Tenda e Prédio anexo), nas casas (GC's - Grupos de Comunhão) e onde quer que a comunidade esteja reunida. "
        "A igreja é cuidada pela equipe pastoral, diáconos, líderes de ministérios e equipe administrativa."
    ),

    # ── Membresia ──
    (
        "membresia",
        "Níveis de comprometimento na igreja",
        "Existem quatro níveis de comprometimento: "
        "1) VISITANTE: Deve ser bem recebido e amado. Dele não se cobra nada, exceto respeito pelas normas dos cultos e dos eventos. "
        "2) CONGREGADO: É mais frequente que um visitante aos cultos e atividades. Já tem a igreja como sua casa espiritual. Pode ajudar esporadicamente em alguma atividade. Para se tornar membro, deve ser batizado e passar pelo Curso de Membresia. "
        "3) MEMBRO: Assumiu o compromisso de pertencer ao corpo de Cristo em uma expressão local. Tem direito a participar plenamente da vida da igreja, votar em deliberações, receber cuidados pastorais. É chamado a viver de modo digno do evangelho, servir com seus dons, contribuir financeiramente, zelar pela unidade da igreja. "
        "4) MEMBRO EM SERVIÇO VOLUNTÁRIO: Membros ativos em um ou mais Ministérios, liderando ou compondo equipes ministeriais. Formam o coração da igreja. Deles é exigido um nível maior de comprometimento."
    ),
    (
        "membresia",
        "Direitos e deveres dos membros",
        "Como membro da igreja, você tem o direito de: Participar plenamente da vida da igreja, nos cultos, grupos e ministérios. "
        "Ser edificado pela Palavra. Ter prioridade nos eventos e atividades da Igreja, em caso de vagas limitadas. "
        "Votar em assuntos que exijam deliberações da membresia. Receber cuidados pastorais. "
        "Dar sugestões e emitir críticas que visem o aperfeiçoamento da Igreja. "
        "Como membro da igreja você é chamado a: Viver de modo digno do evangelho. Cultivar sua vida devocional com oração, leitura da Palavra e santificação. "
        "Participar dos cultos e atividades regularmente. Servir com seus dons e talentos. "
        "Contribuir financeiramente. Receber com humildade as disciplinas eclesiásticas. "
        "Zelar pela unidade da igreja. Trabalhar para salvação dos perdidos e avanço do Reino de Deus."
    ),
    (
        "membresia",
        "Pacto de membresia",
        "No pacto de membresia, o membro se compromete a: Amar e honrar a Deus. Buscar ser cheio do Espírito Santo. "
        "Buscar os frutos do Espírito Santo. Conhecer e praticar a Palavra de Deus. "
        "Amar e servir aos irmãos em Cristo. Amar a Igreja. Servir a Deus na Igreja. "
        "Lutar pela comunhão na Igreja. Dar bom testemunho. "
        "Contribuir financeiramente para a manutenção e avanço da Igreja. "
        "Submeter-se às normas e princípios da Igreja. "
        "Cooperar para o crescimento da Igreja e a expansão do Reino de Deus."
    ),
    (
        "membresia",
        "Exclusão de membros",
        "A exclusão de membros, se necessária, segue o modelo ensinado por Jesus em Mateus 18:15-20. "
        "Primeiro, conversa-se a sós com o irmão. Se não resolver, leva-se mais uma ou duas testemunhas. "
        "Se persistir, leva-se à igreja. Se ainda assim se recusar a ouvir, trata-se como alguém de fora."
    ),

    # ── Doutrinas ──
    (
        "doutrina",
        "Princípios fundamentais da fé batista",
        "A igreja se baseia em seis princípios fundamentais: "
        "1) A aceitação das Escrituras Sagradas como única regra de fé e conduta. "
        "2) O conceito de igreja como sendo uma comunidade local, formada de pessoas regeneradas e biblicamente batizadas. "
        "3) A separação entre igreja e Estado. "
        "4) A absoluta liberdade de consciência. "
        "5) A responsabilidade individual diante de Deus. "
        "6) A autenticidade e apostolicidade da igreja."
    ),
    (
        "doutrina",
        "Sobre as Escrituras Sagradas",
        "A Bíblia é a Palavra de Deus em linguagem humana. É o registro da revelação que Deus fez de si mesmo aos homens. "
        "Sendo Deus seu verdadeiro autor, foi escrita por homens inspirados e dirigidos pelo Espírito Santo. "
        "Seu conteúdo é a verdade, sem mescla de erro, e por isso é um perfeito tesouro de instrução divina. "
        "A Bíblia é a autoridade única em matéria de religião, fiel padrão pelo qual devem ser aferidas as doutrinas e a conduta dos homens. "
        "2Pedro 1:20-21; 2Timóteo 3:16-17; Hebreus 4:12; Salmo 119:105."
    ),
    (
        "doutrina",
        "Sobre Deus - Pai, Filho e Espírito Santo (Trindade)",
        "O único Deus vivo e verdadeiro é Espírito pessoal, eterno, infinito e imutável; é onipotente, onisciente e onipresente. "
        "Em sua triunidade, o eterno Deus se revela como Pai, Filho e Espírito Santo, pessoas distintas, mas sem divisão em sua essência. "
        "Deus Pai: Criador, manifesta disposição paternal para com todos os homens. É Pai de Nosso Senhor Jesus Cristo. "
        "Deus Filho: Jesus Cristo, um em essência com o Pai, é o eterno Filho de Deus. É o único Mediador entre Deus e os homens e o único e suficiente Salvador e Senhor. "
        "Deus Espírito Santo: Atuou na criação do mundo e inspirou os homens a escreverem as Sagradas Escrituras. Habita no crente, guia-o em toda a verdade e distribui dons para a edificação do Corpo de Cristo."
    ),
    (
        "doutrina",
        "Sobre o homem e o pecado",
        "O homem foi criado por Deus à sua imagem e semelhança. Criado para a glorificação de Deus, seu propósito é amar, conhecer e estar em comunhão com seu Criador. "
        "Cedendo à tentação de Satanás, o homem caiu no pecado e perdeu a comunhão com Deus. Todos somos, por natureza, pecadores e inclinados à prática do mal. "
        "O pecado maior consiste em não crer na pessoa de Jesus Cristo como Salvador pessoal. "
        "Separado de Deus, o homem é absolutamente incapaz de salvar a si mesmo e depende da Graça de Deus para ser salvo. "
        "Romanos 5:12-19; Romanos 6:23."
    ),
    (
        "doutrina",
        "Sobre a salvação",
        "A Salvação é outorgada por Deus pela sua Graça, mediante arrependimento do pecador e da sua fé em Jesus Cristo como único Salvador e Senhor. "
        "O preço da redenção eterna foi pago por Jesus Cristo na cruz. É um dom gratuito que Deus oferece a todos os homens. "
        "A salvação compreende: Regeneração (nascer de novo), Justificação (ser declarado justo), Santificação (processo de crescimento) e Glorificação (estado final de felicidade). "
        "Há duas condições para ser regenerado: arrependimento e fé. "
        "Efésios 2:8-9; João 3:16-18; Romanos 10:9-10; 2Coríntios 5:17."
    ),
    (
        "doutrina",
        "Sobre eleição e segurança eterna do crente",
        "Eleição é a escolha feita por Deus, em Cristo, desde a eternidade, de pessoas para a vida eterna, segundo a riqueza da sua graça. "
        "Essa eleição está em perfeita consonância com o livre-arbítrio de cada homem. "
        "A salvação do crente é eterna. Os salvos perseveram em Cristo e estão guardados pelo poder de Deus. "
        "Nenhuma força ou circunstância tem poder para separar o crente do amor de Deus em Cristo Jesus. "
        "O novo nascimento, o perdão, a justificação, a adoção como filhos de Deus, a eleição e o dom do Espírito Santo asseguram aos salvos a permanência na graça da salvação."
    ),
    (
        "doutrina",
        "Sobre o batismo e a ceia do Senhor",
        "O batismo e a ceia do Senhor são as duas ordenanças da igreja estabelecidas por Jesus Cristo, ambas de natureza simbólica. "
        "O batismo consiste na imersão do crente em água, após sua pública profissão de fé em Jesus Cristo. Simboliza a morte e sepultamento do velho homem e a ressurreição para uma nova vida. "
        "O batismo é condição para ser membro de uma igreja e deve ser ministrado em nome do Pai, do Filho e do Espírito Santo. "
        "A ceia do Senhor é uma cerimônia comemorativa e proclamadora da morte do Senhor Jesus Cristo. O pão representa seu corpo e o vinho simboliza o seu sangue derramado. "
        "Colossenses 2:12; Marcos 16:16; Romanos 6:3-4; 1Coríntios 11:23-25."
    ),
    (
        "doutrina",
        "Sobre a igreja",
        "Igreja é uma congregação local de pessoas regeneradas e batizadas após profissão de fé. "
        "São constituídas por livre vontade dessas pessoas com finalidade de prestarem culto a Deus, observarem as ordenanças de Jesus, meditarem nos ensinamentos da Bíblia e propagarem o evangelho. "
        "Há nas igrejas duas espécies de oficiais: pastores e diáconos. "
        "No Novo Testamento a palavra 'igreja' também aparece como a reunião universal dos remidos de todos os tempos, o corpo espiritual do Senhor, do qual Ele mesmo é o cabeça. "
        "Colossenses 1:18; Efésios 1:22-23; Hebreus 10:25."
    ),
    (
        "doutrina",
        "Sobre mordomia, dízimos e ofertas",
        "Mordomia é a doutrina bíblica que reconhece Deus como Criador, Senhor e Dono de todas as coisas. "
        "O crente pertence a Deus porque Deus o criou e o remiu em Jesus Cristo. É mordomo (administrador) da vida, das aptidões, do tempo e dos bens. "
        "As Escrituras ensinam que o plano de Deus para o sustento financeiro de sua causa consiste na entrega pelos crentes de dízimos e ofertas. "
        "Devem trazer à igreja sua contribuição sistemática e proporcional com alegria e liberdade, para o sustento do ministério e das obras de evangelização. "
        "Levítico 27:30; Provérbios 3:9-10; 2Coríntios 9:6-7; Salmo 24:1."
    ),
    (
        "doutrina",
        "Sobre evangelização e missões",
        "A missão primordial do povo de Deus é a evangelização do mundo, visando à reconciliação do homem com Deus. "
        "É dever de todo discípulo de Jesus Cristo e de todas as igrejas proclamar o Evangelho, procurando fazer novos discípulos em todas as nações. "
        "As igrejas devem promover a obra de missões, rogando ao Senhor que envie obreiros para a sua seara. "
        "Mateus 28:19-20; Atos 1:8; Marcos 13:10."
    ),
    (
        "doutrina",
        "Sobre família e casamento",
        "A família, criada por Deus para o bem do homem, é a primeira instituição da sociedade. "
        "Sua base é o casamento monogâmico e duradouro, por toda a vida, só podendo ser desfeito pela morte ou pela infidelidade conjugal. "
        "O propósito da família é glorificar a Deus e prover satisfação das necessidades humanas de comunhão, educação, companheirismo e segurança. "
        "Marcos 10:6-9; Efésios 3:14-15; 1Timóteo 5:8."
    ),
    (
        "doutrina",
        "Sobre a morte e o destino eterno",
        "Todos os homens são marcados pela finitude, em consequência do pecado a morte se estende a todos. "
        "A Palavra de Deus assegura a continuidade da consciência e da identidade pessoal após a morte. Com a morte está definido o destino eterno de cada homem. "
        "A morte do crente o transporta para um estado de completa felicidade na presença de Deus (dormir no Senhor). "
        "Os incrédulos entram em estado de separação definitiva de Deus. "
        "A Bíblia proíbe a busca de contato com os mortos e nega a eficácia de atos religiosos para os que já morreram. "
        "João 11:25-26; Hebreus 9:27; Daniel 12:2."
    ),
    (
        "doutrina",
        "Sobre a volta de Jesus e o juízo final",
        "Jesus Cristo voltará a este mundo, pessoal e visivelmente, em grande poder e glória. "
        "Os mortos em Cristo serão ressuscitados e arrebatados. Os mortos sem Cristo também serão ressuscitados. "
        "Todos os homens comparecerão perante o Tribunal de Jesus Cristo para serem julgados segundo suas obras. "
        "Os ímpios condenados sofrerão o castigo eterno, separados de Deus. "
        "Os justos, com corpos glorificados, receberão seus galardões e habitarão para sempre no céu com o Senhor. "
        "Romanos 3:20-24; Provérbios 11:23."
    ),
    (
        "doutrina",
        "Sobre liberdade religiosa e ordem social",
        "Deus e somente Deus é o Senhor da consciência. A liberdade religiosa é um dos direitos fundamentais do homem. "
        "A Igreja e o Estado devem estar separados. O Estado deve ser laico e a Igreja livre. "
        "Como sal da terra e luz do mundo, o cristão tem o dever de participar em todo esforço que tende ao bem comum da sociedade. "
        "Devemos estender a mão de ajuda aos órfãos, viúvas, anciãos, enfermos e necessitados, no espírito de amor."
    ),
]
