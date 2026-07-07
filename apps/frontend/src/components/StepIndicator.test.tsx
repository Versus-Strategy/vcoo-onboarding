import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import StepIndicator from './StepIndicator';

const pasos = ['Registro', 'Google', 'Trello', 'Fin'];

describe('StepIndicator', () => {
  it('renderiza todas las etiquetas de los pasos', () => {
    render(
      <StepIndicator pasoActual={0} pasoCompletado={0} pasosTotales={4} pasos={pasos} />
    );
    for (const p of pasos) {
      expect(screen.getByText(p)).toBeInTheDocument();
    }
  });

  it('calcula el porcentaje a partir de pasoCompletado', () => {
    // pasosReales = 4 - 1 = 3; completado 3 -> 100%
    render(
      <StepIndicator pasoActual={3} pasoCompletado={3} pasosTotales={4} pasos={pasos} />
    );
    expect(screen.getByText('100% completo')).toBeInTheDocument();
  });

  it('usa el prop progreso cuando se proporciona', () => {
    render(
      <StepIndicator
        pasoActual={1}
        pasoCompletado={1}
        pasosTotales={4}
        pasos={pasos}
        progreso={42}
      />
    );
    expect(screen.getByText('42% completo')).toBeInTheDocument();
  });

  it('invoca onStepClick para un paso desbloqueado', async () => {
    const onStepClick = vi.fn();
    render(
      <StepIndicator
        pasoActual={0}
        pasoCompletado={2}
        pasosTotales={4}
        pasos={pasos}
        onStepClick={onStepClick}
      />
    );
    await userEvent.click(screen.getByText('Registro'));
    expect(onStepClick).toHaveBeenCalledWith(0);
  });

  it('no invoca onStepClick para un paso bloqueado', async () => {
    const onStepClick = vi.fn();
    render(
      <StepIndicator
        pasoActual={0}
        pasoCompletado={0}
        pasosTotales={4}
        pasos={pasos}
        onStepClick={onStepClick}
        maxUnlocked={0}
      />
    );
    // 'Fin' (idx 3) está bloqueado
    await userEvent.click(screen.getByText('Fin'));
    expect(onStepClick).not.toHaveBeenCalled();
  });
});
