export function ErrorNotice({ message, detail }: { message: string; detail?: string }) {
  return (
    <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      <p className="font-medium">{message}</p>
      {detail && <p className="mt-1 text-xs text-rose-600">{detail}</p>}
    </div>
  );
}
