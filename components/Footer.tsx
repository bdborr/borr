import Link from "next/link";

export default function Footer() {
  return (
    <footer className="bg-gray-900 text-gray-400 py-8 border-t border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex flex-col items-center md:items-start">
            <span className="text-white font-bold text-lg">BORR</span>
            <span className="text-sm mt-1">Research for a Better Bangladesh.</span>
          </div>
          
          <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm">
            <Link href="/about" className="hover:text-white transition-colors">About</Link>
            <Link href="/submit" className="hover:text-white transition-colors">Submit Paper</Link>
            <Link href="/contact" className="hover:text-white transition-colors">Contact</Link>
            <Link href="/terms" className="hover:text-white transition-colors">Terms</Link>
            <Link href="/policy" className="hover:text-white transition-colors">Policy</Link>
            <a href="https://github.com/borr-archive" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">GitHub</a>
          </div>
        </div>
        
        <div className="mt-8 border-t border-gray-800 pt-8 flex justify-center items-center text-xs">
          <p>&copy; {new Date().getFullYear()} Bangladesh Open Research Repository.</p>
        </div>
      </div>
    </footer>
  );
}
