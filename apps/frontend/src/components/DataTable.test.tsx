import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DataTable from './DataTable';

const columns = [
  { accessor: 'name', label: 'Nombre' },
  { accessor: 'status', label: 'Estado' },
];

const data = [
  { name: 'Acme', status: 'activo' },
  { name: 'Globex', status: 'pausado' },
];

describe('DataTable', () => {
  it('renderiza cabeceras y filas', () => {
    render(<DataTable columns={columns} data={data} />);
    expect(screen.getByText('Nombre')).toBeInTheDocument();
    expect(screen.getByText('Acme')).toBeInTheDocument();
    expect(screen.getByText('Globex')).toBeInTheDocument();
  });

  it('muestra el estado vacío cuando no hay datos', () => {
    render(
      <DataTable
        columns={columns}
        data={[]}
        emptyState={{ title: 'Sin clientes', description: 'Crea uno' }}
      />
    );
    expect(screen.getByText('Sin clientes')).toBeInTheDocument();
    expect(screen.getByText('Crea uno')).toBeInTheDocument();
  });

  it('muestra el esqueleto de carga cuando loading', () => {
    const { container } = render(
      <DataTable columns={columns} data={[]} loading />
    );
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('usa la función render de la columna si existe', () => {
    const cols = [
      {
        accessor: 'status',
        label: 'Estado',
        render: (value: unknown) => <span data-testid="custom">[{String(value)}]</span>,
      },
    ];
    render(<DataTable columns={cols} data={[{ status: 'ok' }]} />);
    expect(screen.getByTestId('custom')).toHaveTextContent('[ok]');
  });
});
