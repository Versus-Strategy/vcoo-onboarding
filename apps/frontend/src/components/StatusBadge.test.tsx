import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatusBadge from './StatusBadge';

describe('StatusBadge', () => {
  it('muestra la etiqueta traducida para un estado conocido', () => {
    render(<StatusBadge estado="en-linea" />);
    expect(screen.getByText('En línea')).toBeInTheDocument();
  });

  it('aplica la clase de color del estado', () => {
    render(<StatusBadge estado="fuera-de-linea" />);
    const badge = screen.getByText('Fuera de línea');
    expect(badge.className).toContain('bg-red-100');
  });

  it('usa fallback gris y muestra el estado crudo si es desconocido', () => {
    render(<StatusBadge estado="explotando" />);
    const badge = screen.getByText('explotando');
    expect(badge.className).toContain('bg-gray-100');
  });

  it('mapea configurando al color violeta (identidad VERSUS)', () => {
    render(<StatusBadge estado="configurando" />);
    const badge = screen.getByText('Configurando');
    expect(badge.className).toContain('bg-primary-100');
  });
});
