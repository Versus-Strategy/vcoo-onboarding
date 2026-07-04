import React from 'react';

interface GridProps {
  children: React.ReactNode;
  columns?: number;
  className?: string;
}

const Grid: React.FC<GridProps> = ({ children, columns = 3, className = '' }) => {
  const gridCols = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
  };

  return (
    <div className={`grid gap-4 ${gridCols[columns as keyof typeof gridCols] || gridCols[3]} ${className}`}>
      {children}
    </div>
  );
};

export default Grid;
