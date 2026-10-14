import { useEffect } from 'react'
import { useLocation } from 'react-router'
import { Mascot } from '../components/Mascot/Mascot'
import { useDaily } from '../hooks/useDaily'
import { usePlayer } from '../hooks/usePlayer'
import styles from './TextPage.module.css'

export function AboutPage() {
  const { ready } = usePlayer()
  const { data } = useDaily(ready)
  const { hash } = useLocation()

  useEffect(() => {
    document.title = 'Sobre, fontes e privacidade | Músicas Babuínas'
  }, [])

  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: 'start' })
  }, [hash])

  const demo = data?.audio.demo_mode

  return (
    <div className="page">
      <header className={styles.hero}>
        <div>
          <p className="eyebrow">Bastidores</p>
          <h1 className={styles.title}>Sobre o Músicas Babuínas</h1>
          <p className={styles.lead}>
            Um jogo diário de adivinhação musical feito com carinho, humor e muito rock. O
            Babuíno do Rock é o mascote original do projeto.
          </p>
        </div>
        <Mascot mood="champion" size={130} decorative />
      </header>

      <section id="fontes" className={styles.section}>
        <h2 className={styles.sectionTitle}>Fontes musicais</h2>
        <p>
          <strong>Áudio em uso agora:</strong>{' '}
          {data ? (demo ? 'modo demonstração' : data.audio.attribution ?? data.audio.provider) : '…'}
          .
        </p>
        <h3>Modo demonstração</h3>
        <p>
          Quando o servidor não tem um provedor de áudio licenciado configurado, o jogo usa um
          catálogo à parte com melodias em <strong>domínio público</strong> (compositores falecidos
          há mais de 70 anos ou canções tradicionais). Os arranjos são sintetizados pelo próprio
          jogo, em estilos inspirados em cada categoria, sem gravações de terceiros. Esse catálogo
          serve para testar e demonstrar o jogo — ele não é o catálogo musical definitivo.
        </p>
        <h3>Músicas: as mais ouvidas no Spotify</h3>
        <p>
          O catálogo principal reúne 100 músicas por categoria, escolhidas pelos números de{' '}
          <strong>streams no Spotify</strong> publicados pelo{' '}
          <a href="https://kworb.net/spotify/" target="_blank" rel="noreferrer noopener">
            kworb.net
          </a>
          . A categoria Geral segue a lista global das mais tocadas de todos os tempos; nas outras,
          as músicas de artistas de cada gênero são ordenadas pelo total de streams. Cada arquivo
          do catálogo registra a fonte, a data da consulta e a posição. Esses dados são de
          terceiros, não uma parada oficial do Spotify. No fim da partida, o botão “Ouvir no
          Spotify” leva à faixa completa.
        </p>
        <h3>Áudio: trechos da gravação original</h3>
        <p>
          O jogo toca a gravação original, por partes: a cada tentativa o trecho fica maior. O
          áudio vem das prévias oficiais da API pública do Deezer, porque a política para
          desenvolvedores do Spotify não permite usar o conteúdo dele em jogos e quizzes. O
          servidor entrega só o trecho já liberado, sem nome nem metadados, e mostra a atribuição
          ao Deezer no fim. Os direitos das gravações pertencem aos respectivos titulares.
        </p>
      </section>

      <section id="privacidade" className={styles.section}>
        <h2 className={styles.sectionTitle}>Privacidade</h2>
        <ul className={styles.list}>
          <li>
            Não pedimos nome, e-mail, telefone nem senha. Ao abrir o jogo, o servidor cria um{' '}
            <strong>identificador anônimo aleatório</strong>, guardado no seu navegador
            (localStorage). No servidor fica apenas um resumo criptográfico (hash) dele.
          </li>
          <li>
            Guardamos suas partidas (categoria, data, palpites digitados, tentativas e pontos) para
            calcular resultados, estatísticas e o histórico.
          </li>
          <li>
            Não guardamos endereço IP nem usamos cookies de rastreamento, anúncios ou ferramentas de
            analytics de terceiros. O IP é usado apenas em memória, por alguns minutos, para limitar
            abusos.
          </li>
          <li>
            <strong>Retenção:</strong> identificadores sem atividade por mais de 400 dias podem ser
            apagados junto com as partidas associadas.
          </li>
          <li>
            <strong>Exclusão:</strong> apagar os dados do site no navegador desvincula este aparelho
            imediatamente (as estatísticas recomeçam do zero). Para apagar também os registros no
            servidor, entre em contato com a pessoa responsável pela publicação informando o
            identificador.
          </li>
          <li>
            Limitação conhecida: sem login, as estatísticas ficam presas a este navegador. Trocar de
            aparelho ou limpar os dados começa um novo histórico.
          </li>
        </ul>
      </section>

      <section id="termos" className={styles.section}>
        <h2 className={styles.sectionTitle}>Termos de uso</h2>
        <ul className={styles.list}>
          <li>O jogo é gratuito, para diversão, e pode mudar ou sair do ar sem aviso.</li>
          <li>
            É proibido automatizar palpites, sobrecarregar o servidor ou tentar descobrir respostas
            por meios técnicos. Os limites de requisição existem para manter o palco de pé.
          </li>
          <li>
            Marcas, nomes de artistas e músicas pertencem aos seus titulares e são citados apenas
            para identificação. Projeto independente, sem afiliação com o Bandle, gravadoras ou
            serviços de streaming.
          </li>
        </ul>
      </section>
    </div>
  )
}
