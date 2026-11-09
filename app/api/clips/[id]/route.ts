import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY! // Usa la service role para borrar
);

export async function DELETE(
  req: Request,
  { params }: { params: { id: string } }
) {
  const { id } = params;

  // 1. Buscar el clip para obtener la ruta del archivo
  const { data: clip, error: fetchError } = await supabase
    .from('clips')
    .select('storage_path')
    .eq('id', id)
    .single();

  if (fetchError || !clip) {
    return NextResponse.json({ error: 'Clip no encontrado' }, { status: 404 });
  }

  // 2. Borrar el archivo de Storage
  if (clip.storage_path) {
    const { error: storageError } = await supabase.storage
      .from('clips')
      .remove([clip.storage_path]);
    if (storageError) {
      console.error('Error borrando archivo:', storageError);
    }
  }

  // 3. Borrar el registro de la tabla
  const { error: deleteError } = await supabase
    .from('clips')
    .delete()
    .eq('id', id);

  if (deleteError) {
    return NextResponse.json({ error: deleteError.message }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
