import React from 'react';
import { ArrowPathIcon } from './icons';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

const variantClasses = {
  primary: 'bg-primary-600 text-white hover:bg-primary-700 focus-visible:ring-primary-300 disabled:bg-primary-300 disabled:text-white',
  secondary: 'bg-gray-200 text-gray-700 hover:bg-gray-300 focus-visible:ring-gray-400 disabled:bg-gray-100 disabled:text-gray-400',
  ghost: 'text-primary-600 hover:bg-primary-50 focus-visible:ring-primary-300 disabled:text-gray-300',
};

const sizeClasses = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
};

const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  children,
  className = '',
  disabled,
  ...props
}) => {
  return (
    <button
      className={`inline-flex items-center justify-center font-medium rounded-lg transition-colors duration-200 cursor-pointer focus-ring ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && (
        <ArrowPathIcon className="animate-spin motion-reduce:animate-none -ml-1 mr-2 h-4 w-4" />
      )}
      {children}
    </button>
  );
};

export default Button;
