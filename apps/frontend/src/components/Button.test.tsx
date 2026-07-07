import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Button from './Button';

describe('Button', () => {
  it('renderiza sus children', () => {
    render(<Button>Guardar</Button>);
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeInTheDocument();
  });

  it('llama a onClick cuando se pulsa', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('está deshabilitado y no dispara onClick cuando loading', async () => {
    const onClick = vi.fn();
    render(<Button loading onClick={onClick}>Cargando</Button>);
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    await userEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('respeta la prop disabled', () => {
    render(<Button disabled>No</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('aplica clases de la variante secondary', () => {
    render(<Button variant="secondary">Sec</Button>);
    expect(screen.getByRole('button').className).toContain('bg-gray-200');
  });

  it('muestra un spinner cuando loading', () => {
    const { container } = render(<Button loading>X</Button>);
    expect(container.querySelector('svg.animate-spin')).toBeTruthy();
  });
});
