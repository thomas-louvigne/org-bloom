;;; make-org-roam-test-site.el --- Build test-sites/04-org-roam-jardin with org-roam itself -*- lexical-binding: t -*-

;; Creates a real org-roam graph through org-roam's own commands (node
;; capture, dailies, tags, aliases, refs, headline IDs, id: links), so
;; org-bloom is tested on files exactly as org-roam writes them.
;;
;; Usage, from the repository root (installs org-roam from MELPA into a
;; throwaway folder, your own Emacs setup is not touched):
;;
;;   emacs --batch -Q -l scripts/make-org-roam-test-site.el
;;
;; Node file names carry the creation time, so a new run renames them.

(defvar work-dir (make-temp-file "org-roam-test-" t))
(defvar roam-dir (expand-file-name "test-sites/04-org-roam-jardin/"))

(when (file-directory-p roam-dir)
  (dolist (f (directory-files-recursively roam-dir "\\.org\\'"))
    (delete-file f)))
(make-directory (expand-file-name "daily" roam-dir) t)

(setq make-backup-files nil)
(setq user-emacs-directory (file-name-as-directory work-dir))
(setq package-user-dir (expand-file-name "elpa" work-dir))
(require 'package)
(add-to-list 'package-archives '("melpa" . "https://melpa.org/packages/") t)
(package-initialize)
(unless (package-installed-p 'org-roam)
  (package-refresh-contents)
  (package-install 'org-roam))
(require 'org-roam)
(require 'org-roam-dailies)
(setq org-roam-directory roam-dir
      org-roam-db-location (expand-file-name "org-roam.db" work-dir)
      org-id-locations-file (expand-file-name "org-id-locations" work-dir)
      org-roam-capture-templates
      '(("d" "default" plain "%?"
         :target (file+head "%<%Y%m%d%H%M%S>-${slug}.org" "#+title: ${title}\n")
         :unnarrowed t :immediate-finish t))
      org-roam-dailies-capture-templates
      '(("d" "default" entry "* %?"
         :target (file+head "%<%Y-%m-%d>.org" "#+title: %<%Y-%m-%d>\n")
         :immediate-finish t)))
(org-roam-db-autosync-mode 1)

(defun new-node (title)
  "Create a node the way org-roam-node-find does, return its file."
  (org-roam-capture- :node (org-roam-node-create :title title) :props '(:finalize find-file))
  (save-buffer)
  (prog1 (buffer-file-name) (kill-buffer)))

(defun link (title)
  "An id: link as org-roam-node-insert writes it."
  (let ((node (org-roam-node-from-title-or-alias title)))
    (org-link-make-string (concat "id:" (org-roam-node-id node)) title)))

(defun edit (file fn)
  (with-current-buffer (find-file-noselect file)
    (goto-char (point-max))
    (funcall fn)
    (save-buffer)
    (org-roam-db-update-file)
    (kill-buffer)))

(let ((home (new-node "Accueil"))
      (zk (new-node "Zettelkasten"))
      (ete (new-node "Été à Montréal"))
      (priv (new-node "Journal intime"))
      (cuisine (new-node "Cuisine")))
  (org-roam-db-sync)
  ;; Tags, aliases and refs set with org-roam's own commands, on the file node.
  (with-current-buffer (find-file-noselect zk)
    (goto-char (point-min))
    (org-roam-tag-add '("methode" "notes"))
    (org-roam-alias-add "ZK")
    (org-roam-ref-add "https://zettelkasten.de")
    (save-buffer) (kill-buffer))
  (with-current-buffer (find-file-noselect priv)
    (goto-char (point-min))
    (org-roam-tag-add '("noexport"))
    (save-buffer) (kill-buffer))
  (org-roam-db-sync)
  ;; A headline node in Cuisine.
  (edit cuisine (lambda ()
                  (insert "\nQuelques recettes.\n\n* Tarte aux pommes :dessert:\n")
                  (org-id-get-create)
                  (goto-char (point-max))
                  (insert "Des pommes, de la pâte.\n\n* Secret :noexport:\nRecette de grand-mère.\n")))
  (org-roam-db-sync)
  (edit zk (lambda () (insert "\nUne méthode de prise de notes. Voir " (link "Accueil") ".\n")))
  (edit ete (lambda () (insert "\nVacances <2026-07-14 Tue>. Lire " (link "ZK") " et manger une "
                               (link "Tarte aux pommes") ".\n")))
  (edit home (lambda ()
               (insert "\nBienvenue.\n\n- " (link "Zettelkasten") "\n- " (link "Été à Montréal")
                       "\n- " (link "Tarte aux pommes") "\n- " (link "Journal intime") "\n"
                       "- un lien roam: [[roam:Cuisine]]\n- un lien fuzzy: [[Cuisine]]\n")))
  (edit priv (lambda () (insert "\nRien à voir ici. " (link "Accueil") "\n"))))
;; Two dailies, through org-roam-dailies' own capture.
(dolist (d '((2026 10 11) (2026 10 12)))
  (org-roam-dailies--capture (encode-time (list 0 0 9 (nth 2 d) (nth 1 d) (nth 0 d) nil nil nil)) t "d") (save-buffer) (kill-buffer)
  (edit (expand-file-name (format "daily/%d-%02d-%02d.org" (nth 0 d) (nth 1 d) (nth 2 d)) org-roam-directory)
        (lambda () (insert "Note du jour, voir " (link "Cuisine") ".\n"))))
(org-roam-db-sync)
(princ (format "nodes in org-roam db: %S\n" (mapcar #'org-roam-node-title (org-roam-node-list))))
(princ (format "links in org-roam db: %d\n" (caar (org-roam-db-query [:select (funcall count *) :from links :where (= type "id")]))))
