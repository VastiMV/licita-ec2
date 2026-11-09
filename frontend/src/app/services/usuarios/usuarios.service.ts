import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  UsuarioRequest,
  UsuarioResponse,
  UsuariosPagina,
  UsuariosParams,
} from '../../contracts/usuarios/usuario.contracts';
import { ApiClient } from '../../core/api/api-client';
import { ENDPOINTS } from '../../core/api/endpoints';

/** Quem acessa o produto — só o super usuário chega aqui (o backend
 * responde 403 a qualquer outro). A exceção é o perfil: cada um edita o seu. */
@Injectable({ providedIn: 'root' })
export class UsuariosService {
  private readonly api = inject(ApiClient);

  listar(params: UsuariosParams = {}): Observable<UsuariosPagina> {
    return this.api.get<UsuariosPagina>(ENDPOINTS.usuarios.lista, { ...params });
  }

  criar(usuario: UsuarioRequest): Observable<UsuarioResponse> {
    return this.api.post<UsuarioResponse, UsuarioRequest>(ENDPOINTS.usuarios.lista, usuario);
  }

  atualizar(id: number, usuario: UsuarioRequest): Observable<UsuarioResponse> {
    return this.api.put<UsuarioResponse, UsuarioRequest>(ENDPOINTS.usuarios.detalhe(id), usuario);
  }

  /** A própria foto, já reduzida (ver `reduzirFoto`). */
  trocarFoto(foto: string): Observable<UsuarioResponse> {
    return this.api.put<UsuarioResponse, { foto: string }>(ENDPOINTS.usuarios.foto, { foto });
  }

  tirarFoto(): Observable<UsuarioResponse> {
    return this.api.delete<UsuarioResponse>(ENDPOINTS.usuarios.foto);
  }

  perfil(): Observable<UsuarioResponse> {
    return this.api.get<UsuarioResponse>(ENDPOINTS.usuarios.perfil);
  }

  /** O super usuário não muda por aqui — o backend ignora o campo. */
  atualizarPerfil(usuario: UsuarioRequest): Observable<UsuarioResponse> {
    return this.api.put<UsuarioResponse, UsuarioRequest>(ENDPOINTS.usuarios.perfil, usuario);
  }

  remover(id: number): Observable<void> {
    return this.api.delete<void>(ENDPOINTS.usuarios.detalhe(id));
  }
}
