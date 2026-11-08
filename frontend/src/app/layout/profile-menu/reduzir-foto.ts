/**
 * Reduz a foto escolhida a um quadrado de 256×256 (corte no centro), em JPEG.
 * Fica em ~20–40 KB: vai direto no cadastro do usuário, sem depender do
 * armazenamento de arquivos (ver `User.foto` no backend).
 */
export const LADO_DA_FOTO = 256;
export const TAMANHO_MAXIMO_DO_ARQUIVO = 15 * 1024 * 1024;

export async function reduzirFoto(arquivo: File): Promise<string> {
  if (!arquivo.type.startsWith('image/')) throw new Error('Escolha uma imagem (JPG, PNG ou WEBP).');
  if (arquivo.size > TAMANHO_MAXIMO_DO_ARQUIVO)
    throw new Error('Imagem grande demais (máximo 15 MB).');
  const imagem = await createImageBitmap(arquivo);
  const lado = Math.min(imagem.width, imagem.height);
  const tela = document.createElement('canvas');
  tela.width = LADO_DA_FOTO;
  tela.height = LADO_DA_FOTO;
  const contexto = tela.getContext('2d');
  if (!contexto) throw new Error('Não foi possível preparar a imagem.');
  contexto.drawImage(
    imagem,
    (imagem.width - lado) / 2,
    (imagem.height - lado) / 2,
    lado,
    lado,
    0,
    0,
    LADO_DA_FOTO,
    LADO_DA_FOTO,
  );
  imagem.close();
  return tela.toDataURL('image/jpeg', 0.85);
}
