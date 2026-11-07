import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

/**
 * Marca "Inside Solutions". Único lugar que desenha isso — usado pela
 * `Sidebar`, pela topbar mobile e pela página de login.
 *
 * As imagens ficam em `public/marca/` (fundo transparente, cores originais
 * do logo). O logo é claro, feito para fundo escuro: quem usa a marca põe
 * ela sobre `--color-marca-fundo` (a faixa do topo do menu, o topo do
 * login). No modo `compact` a própria marca traz esse fundo, num quadrado,
 * porque aparece também sobre fundo branco (topbar mobile).
 *
 * - padrão: símbolo + "INSIDE SOLUTIONS LTDA" (menu);
 * - `[completo]`: com a frase "Construindo resultados…" (login);
 * - `[compact]`: só o símbolo "iS" (menu recolhido, topbar mobile, favicon).
 */
@Component({
  selector: 'app-brand',
  imports: [RouterLink],
  templateUrl: './brand.component.html',
  styleUrl: './brand.component.scss',
})
export class BrandComponent {
  readonly compact = input(false);
  readonly completo = input(false);

  protected imagem(): string {
    if (this.compact()) return 'marca/simbolo.png';
    return this.completo() ? 'marca/logo-completo.png' : 'marca/logo-horizontal.png';
  }
}
