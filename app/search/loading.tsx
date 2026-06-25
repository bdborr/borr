export default function SearchLoading() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col md:flex-row gap-4 md:gap-8 animate-pulse">
      <aside className="w-full md:w-64 shrink-0 hidden md:block">
        <div className="bg-white dark:bg-gray-900 p-6 rounded-lg border border-gray-200 dark:border-gray-800 space-y-6">
          <div className="h-5 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
          {[...Array(4)].map((_, i) => (
            <div key={i} className="space-y-2">
              <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded" />
              <div className="h-9 w-full bg-gray-100 dark:bg-gray-800 rounded-md" />
            </div>
          ))}
        </div>
      </aside>

      <main className="flex-1 min-w-0">
        <div className="h-[50px] w-full bg-gray-200 dark:bg-gray-700 rounded-md mb-8" />
        <div className="flex justify-between items-end border-b border-gray-200 dark:border-gray-800 pb-4 mb-6">
          <div className="h-7 w-48 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-4 w-24 bg-gray-100 dark:bg-gray-800 rounded" />
        </div>

        <div className="space-y-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-white dark:bg-gray-900 p-6 rounded-lg border border-gray-200 dark:border-gray-800">
              <div className="h-6 w-3/4 bg-gray-200 dark:bg-gray-700 rounded mb-3" />
              <div className="h-4 w-1/2 bg-gray-100 dark:bg-gray-800 rounded mb-4" />
              <div className="space-y-2 mb-4">
                <div className="h-3.5 w-full bg-gray-100 dark:bg-gray-800 rounded" />
                <div className="h-3.5 w-full bg-gray-100 dark:bg-gray-800 rounded" />
                <div className="h-3.5 w-2/3 bg-gray-100 dark:bg-gray-800 rounded" />
              </div>
              <div className="flex gap-2">
                <div className="h-6 w-20 bg-gray-100 dark:bg-gray-800 rounded-md" />
                <div className="h-6 w-24 bg-gray-100 dark:bg-gray-800 rounded-md" />
                <div className="h-6 w-16 bg-gray-100 dark:bg-gray-800 rounded-md" />
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
