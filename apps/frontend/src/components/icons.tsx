/**
 * Iconos centralizados (outline de Heroicons).
 * Re-exporta los iconos de @heroicons/react (https://heroicons.com) para no
 * mantener SVG inline. `ClipboardListIcon` se mapea a
 * `ClipboardDocumentListIcon` (nombre real en heroicons v2).
 */
export {
  EyeIcon,
  EyeSlashIcon,
  ChartBarIcon,
  CpuChipIcon,
  ClipboardDocumentListIcon as ClipboardListIcon,
  GlobeAltIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  ChevronUpDownIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  DocumentTextIcon,
  EnvelopeIcon,
  CalendarIcon,
  CodeBracketIcon,
  PuzzlePieceIcon,
  CheckCircleIcon,
  // nuevos registrados (eran importados directos de heroicons):
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ClipboardIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
