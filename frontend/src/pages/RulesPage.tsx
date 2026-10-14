import { Headphones, Keyboard, Send, Share2, SkipForward, Trophy } from 'lucide-react'
import { useEffect } from 'react'
import { Link } from 'react-router'
import { Mascot } from '../components/Mascot/Mascot'
import { useDaily } from '../hooks/useDaily'
import { usePlayer } from '../hooks/usePlayer'
import { formatSeconds } from '../utils/format'
import styles from './TextPage.module.css'

const DEFAULT_STAGES = [1, 2, 3, 5, 8, 12]
const DEFAULT_SCORES = [100, 80, 60, 40, 20, 10]

export function RulesPage() {
  const { ready } = usePlayer()
  const { data } = useDaily(ready)
  const stages = data?.rules.stages_seconds ?? DEFAULT_STAGES
  const scores = data?.rules.score_table ?? DEFAULT_SCORES
  const max = stages.length

  useEffect(() => {
    document.title = 'Como jogar | Músicas Babuínas'
  }, [])

  return (
    <div className="page">
      <header className={styles.hero}>
        <div>
          <p className="eyebrow">Regras do show</p>
          <h1 className={styles.title}>Como jogar</h1>
          <p className={styles.lead}>
            Todo dia, cada uma das seis categorias ganha uma música secreta — a mesma para todo
            mundo. Descubra o título ouvindo o mínimo possível.
          </p>
        </div>
        <Mascot mood="listening" size={130} decorative />
      </header>

      <ol className={styles.steps}>
        <li>
          <Headphones aria-hidden />
          <div>
            <h2>Aperte o play</h2>
            <p>
              A primeira pista tem só {formatSeconds(stages[0])}. Você pode ouvir quantas vezes
              quiser — ouvir não gasta tentativa.
            </p>
          </div>
        </li>
        <li>
          <Keyboard aria-hidden />
          <div>
            <h2>Digite o título</h2>
            <p>
              Comece a digitar e escolha nas sugestões, ou envie o texto do jeito que estiver.
              Acentos, maiúsculas, pontuação e pequenos erros de digitação não atrapalham. A resposta
              é o <strong>título da música</strong>, não o nome do artista.
            </p>
          </div>
        </li>
        <li>
          <SkipForward aria-hidden />
          <div>
            <h2>Errou ou pulou? Mais música!</h2>
            <p>
              Cada palpite errado ou pulo usa uma das {max} tentativas e libera um trecho maior.
              Repetir um palpite já feito não conta.
            </p>
          </div>
        </li>
        <li>
          <Send aria-hidden />
          <div>
            <h2>Acertou, acabou</h2>
            <p>
              A partida termina no acerto ou quando as tentativas acabam — aí o babuíno revela a
              música. Depois do fim, todos os trechos ficam liberados para ouvir de novo.
            </p>
          </div>
        </li>
        <li>
          <Share2 aria-hidden />
          <div>
            <h2>Compartilhe sem spoiler</h2>
            <p>O resultado vira uma sequência de quadradinhos que não entrega a música.</p>
          </div>
        </li>
      </ol>

      <section className={styles.section} aria-labelledby="pistas">
        <h2 id="pistas" className={styles.sectionTitle}>
          As pistas
        </h2>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Tentativa</th>
                <th scope="col">Trecho liberado</th>
                <th scope="col">Pontos no acerto</th>
              </tr>
            </thead>
            <tbody>
              {stages.map((seconds, i) => (
                <tr key={seconds}>
                  <td>{i + 1}ª</td>
                  <td>{formatSeconds(seconds)}</td>
                  <td>
                    <strong>{scores[i]}</strong>
                  </td>
                </tr>
              ))}
              <tr>
                <td>Derrota</td>
                <td>música revelada</td>
                <td>0</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className={styles.note}>
          Os trechos começam sempre do mesmo ponto e vão crescendo. Pontuação e tempos são
          calculados pelo servidor — nada de trapaça pelo navegador.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="diario">
        <h2 id="diario" className={styles.sectionTitle}>
          <Trophy aria-hidden size={20} /> Desafio diário e sequência
        </h2>
        <p>
          Os desafios viram à <strong>meia-noite no horário de Brasília</strong> (fuso{' '}
          {data?.timezone ?? 'America/Sao_Paulo'}), para todos os jogadores ao mesmo tempo. Cada
          categoria pode ser jogada uma vez por dia; recarregar a página não troca a música nem
          reinicia a partida. Jogue pelo menos uma categoria por dia para manter sua sequência de
          dias.
        </p>
        <p>
          <Link to="/" className="btn btn-primary">
            Bora jogar!
          </Link>
        </p>
      </section>
    </div>
  )
}
