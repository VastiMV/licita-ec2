import { Component, forwardRef, input, signal } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface SelectOption {
  readonly value: string;
  readonly label: string;
}

let nextId = 0;

/**
 * `<select>` reutilizável — único componente de seleção do projeto.
 * Recebe as opções via `[options]` (ver `contracts/licitacoes/modalidade.ts`
 * para um exemplo de lista compartilhada) em vez de cada página escrever
 * seu próprio conjunto de `<option>`.
 *
 * Estado interno é `signal` pelo mesmo motivo do `InputTextComponent`: um
 * `writeValue` precisa de `set()` para re-renderizar em Angular zoneless.
 */
@Component({
  selector: 'app-select',
  templateUrl: './select.component.html',
  styleUrl: './select.component.scss',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => SelectComponent),
      multi: true,
    },
  ],
})
export class SelectComponent implements ControlValueAccessor {
  readonly label = input('');
  readonly options = input.required<readonly SelectOption[]>();
  readonly placeholder = input('Todas');
  /** `false` tira a opção vazia (o placeholder) — para campos que sempre
   * têm um valor escolhido, como um período. */
  readonly opcaoVazia = input(true);
  readonly error = input<string | null>(null);

  protected readonly selectId = `select-${++nextId}`;
  protected readonly value = signal('');
  protected readonly disabled = signal(false);

  private onChange: (value: string) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(value: string | null): void {
    this.value.set(value ?? '');
  }

  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled.set(isDisabled);
  }

  protected handleChange(rawValue: string): void {
    this.value.set(rawValue);
    this.onChange(rawValue);
  }

  protected handleBlur(): void {
    this.onTouched();
  }
}
