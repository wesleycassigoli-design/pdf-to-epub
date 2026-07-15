import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Política de Privacidade | PDF → EPUB3",
};

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen px-6 py-12">
      <div className="max-w-2xl mx-auto">
        <Link
          href="/login"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-ink mb-8 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar
        </Link>

        <img src="/logo-afya.svg" alt="Afya" className="h-9 w-auto mb-6" />

        <h1 className="text-2xl font-display font-semibold text-ink mb-2">
          Política de Privacidade
        </h1>
        <p className="text-xs text-gray-500 mb-10">Última atualização: julho de 2026</p>

        <div className="space-y-8 text-sm text-gray-700 leading-relaxed">
          <section>
            <h2 className="text-base font-semibold text-ink mb-2">1. Finalidade do tratamento</h2>
            <p>
              Esta plataforma converte arquivos PDF e DOCX em EPUB3 para uso educacional interno.
              Os dados pessoais e os arquivos enviados são tratados exclusivamente para viabilizar
              o cadastro, a autenticação, o controle de acesso (aprovação manual de novos usuários)
              e a execução das conversões solicitadas pelo próprio usuário.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink mb-2">2. Dados coletados</h2>
            <ul className="list-disc list-inside space-y-1">
              <li><strong className="text-ink">Dados de cadastro</strong>: nome completo e e-mail corporativo (@afya.com.br).</li>
              <li><strong className="text-ink">Dados de acesso</strong>: data de criação da conta, data do último login, status de aprovação.</li>
              <li><strong className="text-ink">Arquivos enviados</strong>: os PDFs/DOCX que você envia para conversão, e os EPUBs gerados a partir deles.</li>
            </ul>
            <p className="mt-2">
              A senha é armazenada apenas em formato de hash criptográfico (bcrypt) — nunca em
              texto puro, e não é acessível por administradores da plataforma.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink mb-2">3. Onde os dados ficam armazenados</h2>
            <p>
              Todos os dados — cadastro de usuários, metadados de conversão e os arquivos (PDF/DOCX
              originais e EPUBs gerados) — são armazenados no <strong className="text-ink">Supabase</strong>,
              provedor de banco de dados (PostgreSQL) e armazenamento de arquivos utilizado por esta
              aplicação como operador dos dados, nos termos do art. 5º, VII da LGPD.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink mb-2">4. Compartilhamento com terceiros</h2>
            <p>
              Os dados não são vendidos, compartilhados ou usados para fins de marketing. O único
              terceiro envolvido é o Supabase, na qualidade de operador técnico de armazenamento.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink mb-2">5. Direitos do titular</h2>
            <p>Nos termos do art. 18 da Lei Geral de Proteção de Dados (Lei nº 13.709/2018), você tem direito a:</p>
            <ul className="list-disc list-inside space-y-1 mt-2">
              <li>Confirmar a existência de tratamento dos seus dados;</li>
              <li>Acessar os seus dados;</li>
              <li>Corrigir dados incompletos, inexatos ou desatualizados;</li>
              <li>Solicitar anonimização, bloqueio ou eliminação de dados desnecessários;</li>
              <li>Solicitar a portabilidade dos seus dados a outro fornecedor;</li>
              <li>Solicitar a eliminação dos dados tratados com o seu consentimento;</li>
              <li>Revogar o consentimento a qualquer momento.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink mb-2">6. Como exercer seus direitos</h2>
            <p>
              Para exercer qualquer um dos direitos acima, ou para esclarecer dúvidas sobre o
              tratamento dos seus dados, entre em contato com o administrador da plataforma através
              do e-mail <strong className="text-ink">{process.env.NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL || "privacidade@afya.com.br"}</strong>.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-ink mb-2">7. Retenção e exclusão</h2>
            <p>
              Os dados são mantidos enquanto sua conta estiver ativa na plataforma. Ao solicitar a
              exclusão da conta, os dados de cadastro e os arquivos associados são removidos do
              Supabase, ressalvadas hipóteses de guarda obrigatória por lei.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
