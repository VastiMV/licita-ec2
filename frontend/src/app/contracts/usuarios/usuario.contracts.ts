/**
 * Contratos da tela de Usuários (Configurações → Usuários). Ver
 * `apps/accounts/serializers.py` (`UsuarioSerializer`) no backend.
 *
 * A senha só vai: nunca volta na resposta. Ao editar, senha vazia quer dizer
 * "manter a atual".
 */

export interface UsuarioResponse {
  readonly id: number;
  /** O nome visual — é o que aparece no histórico de tudo que a pessoa faz. */
  readonly nome: string;
  readonly email: string;
  /** Acessa Configurações: o armazenamento e esta tela. */
  readonly is_superuser: boolean;
  readonly criado_em: string;
  /** Só no próprio perfil (`usuarios/eu/`): `data:image/…` ou vazio (a inicial). */
  readonly foto?: string;
}

export interface UsuarioRequest {
  readonly nome: string;
  readonly email: string;
  readonly is_superuser: boolean;
  readonly senha: string;
}

export interface UsuariosPagina {
  readonly count: number;
  readonly next: string | null;
  readonly previous: string | null;
  readonly results: readonly UsuarioResponse[];
}

export interface UsuariosParams {
  readonly page?: number;
  readonly page_size?: number;
  /** Nome de coluna da tabela, com `-` para descendente (ex.: `-nome`). */
  readonly ordering?: string;
  readonly busca?: string;
}
