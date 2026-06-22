import { createClient } from '@supabase/supabase-js';

const supabaseUrl =
  import.meta.env.VITE_SUPABASE_URL ||
  'https://pdntyfmwjupkhourorfg.supabase.co';
const supabaseAnonKey =
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  'sb_publishable_3mwJkqTensbDnnBD8jVbmw_ihVckMPy';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
