/**
 * Middleware Express de gestion centralisee des erreurs.
 * A placer en dernier dans server.js, apres toutes les routes.
 */
function errorHandler(err, req, res, next) {
  console.error('Erreur :', err.message);

  const status = err.status || 500;
  res.status(status).json({
    erreur: true,
    message: err.message || 'Erreur interne du serveur',
  });
}

module.exports = errorHandler;
